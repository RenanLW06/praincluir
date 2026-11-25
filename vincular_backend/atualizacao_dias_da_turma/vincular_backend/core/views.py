
from django.contrib.auth import authenticate
from django.db import connection
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import planilhas
from .models import (
    Auditoria, Crianca, DiaTurma, Matricula, Ocorrencia, Presenca,
    Realocacao, Sala, Turma, Usuario,
)
from .permissions import AdminEscreveDemaisLeem, EhAdministrador, eh_administrador
from .serializers import (
    AuditoriaSerializer, ChamadaEntradaSerializer, CriancaMonitorSerializer,
    CriancaSerializer, DiaTurmaSerializer, LoginSerializer, MatriculaSerializer,
    OcorrenciaSerializer, PresencaSerializer, RealocacaoSerializer,
    SalaSerializer, TurmaSerializer, UsuarioSerializer,
)
from .services import criancas_visiveis, lista_chamada, turmas_do_usuario, validar_data_da_turma

TAMANHO_MAXIMO_PLANILHA = 5 * 1024 * 1024  # 5 MB


class ContextoAuditoriaMixin:
    """Informa ao banco quem está operando (usado pelos gatilhos de auditoria).

    Funciona porque ATOMIC_REQUESTS=True: o valor vale só dentro da transação da requisição.
    """

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        usuario = request.user
        if usuario and usuario.is_authenticated:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.usuario_id', %s, true)", [str(usuario.pk)])


class BaseViewSet(ContextoAuditoriaMixin, viewsets.ModelViewSet):
    pass


def _data_da_query(request, nome="data", padrao=None):
    valor = request.query_params.get(nome)
    if not valor:
        return padrao
    return serializers.DateField().run_validation(valor)


# ---------------------------------------------------------------- autenticação
class LoginView(ContextoAuditoriaMixin, APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        dados = LoginSerializer(data=request.data)
        dados.is_valid(raise_exception=True)
        usuario = authenticate(
            request=request, username=dados.validated_data["login"], password=dados.validated_data["senha"]
        )
        if usuario is None:
            return Response({"detail": "Login ou senha inválidos."}, status=status.HTTP_400_BAD_REQUEST)
        token, _ = Token.objects.get_or_create(user=usuario)
        return Response({
            "token": token.key,
            "usuario": {"id": usuario.pk, "nome": usuario.nome, "perfil": usuario.perfil},
        })


class LogoutView(ContextoAuditoriaMixin, APIView):
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EuView(ContextoAuditoriaMixin, APIView):
    def get(self, request):
        u = request.user
        return Response({"id": u.pk, "nome": u.nome, "login": u.login, "perfil": u.perfil})


# ---------------------------------------------------------------- cadastros
class UsuarioViewSet(BaseViewSet):
    queryset = Usuario.objects.order_by("nome")
    serializer_class = UsuarioSerializer
    permission_classes = [EhAdministrador]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]  # desativar em vez de apagar
    filterset_fields = ["perfil", "ativo"]
    search_fields = ["nome", "login"]


class CriancaViewSet(BaseViewSet):
    permission_classes = [AdminEscreveDemaisLeem]
    parser_classes = [JSONParser, MultiPartParser, FormParser]  # multipart para a foto
    http_method_names = ["get", "post", "put", "patch", "head", "options"]  # desligar = ativo=false
    filterset_fields = {"ativo": ["exact"], "distrito": ["exact"]}
    search_fields = ["nome", "codigo_v", "responsavel", "codigo_rm"]
    ordering_fields = ["nome", "data_nascimento", "codigo_v"]

    def get_queryset(self):
        consulta = criancas_visiveis(self.request.user)
        if self.request.query_params.get("sem_turma") in ("1", "true"):
            consulta = consulta.exclude(matriculas__data_fim__isnull=True)  # "sem grupo"
        return consulta

    def get_serializer_class(self):
        if eh_administrador(self.request.user):
            return CriancaSerializer
        return CriancaMonitorSerializer

    @action(detail=True, methods=["get"], permission_classes=[EhAdministrador])
    def historico(self, request, pk=None):
        crianca = self.get_object()
        relacionadas = ["matricula", "realocacao", "presenca", "ocorrencia"]
        consulta = Auditoria.objects.filter(
            Q(tabela="crianca", registro_id=crianca.pk)
            | Q(tabela__in=relacionadas, valores_depois__crianca_id=crianca.pk)
            | Q(tabela__in=relacionadas, valores_antes__crianca_id=crianca.pk)
        )
        pagina = self.paginate_queryset(consulta)
        return self.get_paginated_response(AuditoriaSerializer(pagina, many=True).data)


class SalaViewSet(BaseViewSet):
    queryset = Sala.objects.select_related("profissional")
    serializer_class = SalaSerializer
    permission_classes = [AdminEscreveDemaisLeem]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    filterset_fields = ["ativa", "profissional"]
    search_fields = ["nome"]


class DiaTurmaViewSet(BaseViewSet):
    queryset = DiaTurma.objects.all()
    serializer_class = DiaTurmaSerializer
    permission_classes = [AdminEscreveDemaisLeem]
    pagination_class = None


class TurmaViewSet(BaseViewSet):
    serializer_class = TurmaSerializer
    permission_classes = [AdminEscreveDemaisLeem]
    filterset_fields = ["sala", "letra", "horario", "tempo", "ano"]

    def get_queryset(self):
        return (
            turmas_do_usuario(self.request.user)
            .select_related("sala", "letra")
            .annotate(ocupadas=Count("matriculas", filter=Q(matriculas__data_fim__isnull=True)))
        )

    @action(detail=True, methods=["get", "post"], url_path="chamada", permission_classes=[IsAuthenticated])
    def chamada(self, request, pk=None):
        """GET: lista de chamada do dia com situação já registrada.
        POST: grava a chamada inteira de uma vez ({data, registros: [...]})."""
        turma = self.get_object()  # monitor só alcança as turmas das suas salas
        if request.method == "POST":
            entrada = ChamadaEntradaSerializer(data=request.data)
            entrada.is_valid(raise_exception=True)
            data = entrada.validated_data["data"]
            validar_data_da_turma(turma, data)
            self._gravar_chamada(request, turma, data, entrada.validated_data["registros"])
        else:
            data = _data_da_query(request, padrao=timezone.localdate())
            validar_data_da_turma(turma, data)
        return Response(self._montar_chamada(turma, data))

    @staticmethod
    def _gravar_chamada(request, turma, data, registros):
        permitidas = {item["crianca"] for item in lista_chamada(turma.pk, data)}
        vistos, erros = set(), []
        for registro in registros:
            cid = registro["crianca"]
            if cid in vistos:
                erros.append(f"Criança {cid} repetida na chamada.")
            elif cid not in permitidas:
                erros.append(f"Criança {cid} não consta na lista de chamada desta turma nesta data.")
            vistos.add(cid)
        if erros:
            raise serializers.ValidationError({"registros": erros})
        for registro in registros:
            Presenca.objects.update_or_create(
                crianca_id=registro["crianca"], turma=turma, data=data,
                defaults={
                    "situacao": registro["situacao"],
                    "justificativa": registro["justificativa"],
                    "registrado_por": request.user,
                },
            )

    @staticmethod
    def _montar_chamada(turma, data):
        presencas = {p.crianca_id: p for p in Presenca.objects.filter(turma=turma, data=data)}
        criancas = []
        for item in lista_chamada(turma.pk, data):
            p = presencas.get(item["crianca"])
            criancas.append({
                **item,
                "situacao": p.situacao if p else None,
                "justificativa": p.justificativa if p else None,
            })
        return {
            "turma": turma.pk, "sala": turma.sala.nome, "data": data.isoformat(),
            "capacidade": turma.capacidade, "criancas": criancas,
        }


class MatriculaViewSet(BaseViewSet):
    queryset = Matricula.objects.select_related("crianca", "turma")
    serializer_class = MatriculaSerializer
    permission_classes = [EhAdministrador]
    filterset_fields = ["crianca", "turma"]

    def get_queryset(self):
        consulta = super().get_queryset()
        ativa = self.request.query_params.get("ativa")
        if ativa in ("1", "true"):
            consulta = consulta.filter(data_fim__isnull=True)
        elif ativa in ("0", "false"):
            consulta = consulta.filter(data_fim__isnull=False)
        return consulta


class RealocacaoViewSet(BaseViewSet):
    queryset = Realocacao.objects.select_related("crianca")
    serializer_class = RealocacaoSerializer
    permission_classes = [EhAdministrador]
    filterset_fields = {"crianca": ["exact"], "turma_origem": ["exact"], "turma_destino": ["exact"],
                        "data": ["exact", "gte", "lte"]}

    def perform_create(self, serializer):
        serializer.save(realizada_por=self.request.user)


class PresencaViewSet(BaseViewSet):
    serializer_class = PresencaSerializer
    filterset_fields = {"turma": ["exact"], "crianca": ["exact"], "situacao": ["exact"],
                        "data": ["exact", "gte", "lte"]}

    def get_queryset(self):
        return Presenca.objects.filter(turma__in=turmas_do_usuario(self.request.user))

    def get_permissions(self):
        if self.action == "destroy":
            return [EhAdministrador()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(registrado_por=self.request.user)

    def perform_update(self, serializer):
        serializer.save(registrado_por=self.request.user)


class OcorrenciaViewSet(BaseViewSet):
    serializer_class = OcorrenciaSerializer
    filterset_fields = ["crianca", "categoria"]
    search_fields = ["texto"]

    def get_queryset(self):
        return Ocorrencia.objects.select_related("autor").filter(
            crianca__in=criancas_visiveis(self.request.user)
        )

    def get_permissions(self):
        if self.action in ("update", "partial_update", "destroy"):
            return [EhAdministrador()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(autor=self.request.user)


class AuditoriaViewSet(ContextoAuditoriaMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Auditoria.objects.all()
    serializer_class = AuditoriaSerializer
    permission_classes = [EhAdministrador]
    filterset_fields = {"tabela": ["exact"], "registro_id": ["exact"], "usuario_id": ["exact"],
                        "acao": ["exact"], "data_hora": ["gte", "lte"]}


# ---------------------------------------------------------------- planilhas
def _resposta_xlsx(conteudo, nome_arquivo):
    resposta = HttpResponse(conteudo, content_type=planilhas.XLSX_MIME)
    resposta["Content-Disposition"] = f'attachment; filename="{nome_arquivo}"'
    return resposta


CAMPOS_ATUALIZAVEIS = ["nome", "data_nascimento", "responsavel", "telefone", "codigo_rm", "distrito"]


class ImportacaoCriancasView(ContextoAuditoriaMixin, APIView):
    """POST multipart com o campo `arquivo` (.xlsx).

    Sem `?confirmar=1` apenas simula e devolve a prévia. Com `?confirmar=1` grava tudo
    ou nada. A chave é o Código V: existente é atualizado, novo é criado. Células vazias
    não apagam dados já cadastrados.
    """

    permission_classes = [EhAdministrador]
    parser_classes = [MultiPartParser]

    def post(self, request):
        arquivo = request.FILES.get("arquivo")
        if arquivo is None:
            return Response({"detail": "Envie a planilha no campo 'arquivo'."}, status=400)
        if arquivo.size > TAMANHO_MAXIMO_PLANILHA:
            return Response({"detail": "Arquivo maior que 5 MB."}, status=400)
        try:
            linhas = planilhas.ler_linhas(arquivo)
        except planilhas.ErroPlanilha as exc:
            return Response({"detail": str(exc)}, status=400)

        registros, erros = planilhas.validar_linhas(linhas, hoje=timezone.localdate())
        existentes = {
            c.codigo_v: c
            for c in Crianca.objects.filter(codigo_v__in=[r["codigo_v"] for r in registros])
        }
        novas, atualizar, sem_alteracao = [], [], 0
        for r in registros:
            atual = existentes.get(r["codigo_v"])
            if atual is None:
                novas.append(Crianca(**{c: r[c] for c in CAMPOS_ATUALIZAVEIS + ["codigo_v"]}))
                continue
            mudou = False
            for campo in CAMPOS_ATUALIZAVEIS:
                novo = r.get(campo)
                if novo is not None and getattr(atual, campo) != novo:
                    setattr(atual, campo, novo)
                    mudou = True
            if mudou:
                atualizar.append(atual)
            else:
                sem_alteracao += 1

        confirmar = request.query_params.get("confirmar") in ("1", "true", "sim")
        aplicado = False
        if confirmar and not erros:
            Crianca.objects.bulk_create(novas, batch_size=500)
            if atualizar:
                Crianca.objects.bulk_update(atualizar, CAMPOS_ATUALIZAVEIS, batch_size=500)
            aplicado = True

        return Response({
            "aplicado": aplicado,
            "novas": len(novas),
            "atualizadas": len(atualizar),
            "sem_alteracao": sem_alteracao,
            "erros": erros,
            "mensagem": (
                "Importação concluída." if aplicado
                else "Corrija os erros e envie de novo." if erros
                else "Prévia: nada foi gravado. Envie com ?confirmar=1 para aplicar."
            ),
        })


class ModeloImportacaoCriancasView(ContextoAuditoriaMixin, APIView):
    permission_classes = [EhAdministrador]

    def get(self, request):
        return _resposta_xlsx(planilhas.modelo_importacao_criancas(), "modelo_importacao_criancas.xlsx")


class ExportacaoCriancasView(ContextoAuditoriaMixin, APIView):
    permission_classes = [EhAdministrador]

    def get(self, request):
        consulta = Crianca.objects.order_by("nome")
        if request.query_params.get("ativo") in ("1", "true"):
            consulta = consulta.filter(ativo=True)
        cabecalhos = ["nome", "data_nascimento", "codigo_v", "responsavel", "telefone",
                      "codigo_rm", "distrito", "ativo"]
        linhas = [
            [c.nome, c.data_nascimento, c.codigo_v, c.responsavel, c.telefone,
             c.codigo_rm or "", c.distrito or "", "sim" if c.ativo else "não"]
            for c in consulta
        ]
        return _resposta_xlsx(planilhas.gerar_xlsx("criancas", cabecalhos, linhas), "criancas.xlsx")


class ExportacaoPresencasView(ContextoAuditoriaMixin, APIView):
    """GET ?inicio=AAAA-MM-DD&fim=AAAA-MM-DD[&turma=ID][&crianca=ID]"""

    def get(self, request):
        inicio = _data_da_query(request, "inicio")
        fim = _data_da_query(request, "fim")
        if not inicio or not fim:
            return Response({"detail": "Informe 'inicio' e 'fim' (AAAA-MM-DD)."}, status=400)
        consulta = (
            Presenca.objects.select_related("crianca", "turma__sala", "registrado_por")
            .filter(turma__in=turmas_do_usuario(request.user), data__gte=inicio, data__lte=fim)
            .order_by("data", "turma__sala__nome", "crianca__nome")
        )
        for parametro, campo in (("turma", "turma_id"), ("crianca", "crianca_id")):
            valor = request.query_params.get(parametro)
            if valor:
                consulta = consulta.filter(**{campo: valor})
        cabecalhos = ["data", "sala", "turma", "horario", "tempo", "codigo_v", "nome",
                      "situacao", "justificativa", "registrado_por"]
        linhas = [
            [p.data, p.turma.sala.nome, p.turma.letra_id, p.turma.horario, p.turma.tempo,
             p.crianca.codigo_v, p.crianca.nome, p.get_situacao_display(),
             p.justificativa or "", p.registrado_por.nome]
            for p in consulta
        ]
        nome = f"presencas_{inicio.isoformat()}_{fim.isoformat()}.xlsx"
        return _resposta_xlsx(planilhas.gerar_xlsx("presencas", cabecalhos, linhas), nome)
