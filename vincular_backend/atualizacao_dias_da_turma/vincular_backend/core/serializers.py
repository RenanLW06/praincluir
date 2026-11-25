
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers

from .models import (
    Auditoria, Crianca, DiaTurma, Matricula, Ocorrencia, Presenca,
    Realocacao, Sala, Situacao, Turma, Usuario,
)
from .permissions import eh_administrador
from .services import criancas_visiveis, turmas_do_usuario, validar_data_da_turma


def normalizar_justificativa(situacao, justificativa):
    """Justificativa é obrigatória só para ausência justificada; nas demais é descartada."""
    justificativa = (justificativa or "").strip() or None
    if situacao == Situacao.AUSENTE_JUSTIFICADA:
        if not justificativa:
            raise serializers.ValidationError(
                {"justificativa": "A justificativa é obrigatória para ausência justificada."}
            )
        return justificativa
    return None


class LoginSerializer(serializers.Serializer):
    login = serializers.CharField()
    senha = serializers.CharField(write_only=True, trim_whitespace=False)


class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ["id", "nome", "login", "perfil", "ativo", "password", "criado_em"]
        read_only_fields = ["criado_em"]
        extra_kwargs = {"password": {"write_only": True, "required": False}}

    def validate(self, attrs):
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": "A senha é obrigatória."})
        if attrs.get("password"):
            validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):
        senha = validated_data.pop("password")
        return Usuario.objects.create_user(password=senha, **validated_data)

    def update(self, instance, validated_data):
        senha = validated_data.pop("password", None)
        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        if senha:
            instance.set_password(senha)
        instance.save()
        return instance


CAMPOS_PUBLICOS_CRIANCA = [
    "id", "nome", "data_nascimento", "idade", "codigo_v", "responsavel",
    "codigo_rm", "foto", "distrito", "ativo",
]


class CriancaSerializer(serializers.ModelSerializer):
    """Versão completa (administrador): inclui telefone."""

    idade = serializers.SerializerMethodField()

    class Meta:
        model = Crianca
        fields = CAMPOS_PUBLICOS_CRIANCA + ["telefone", "criado_em", "atualizado_em"]
        read_only_fields = ["criado_em", "atualizado_em"]

    def get_idade(self, obj):
        hoje = timezone.localdate()
        nasc = obj.data_nascimento
        return hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))

    def validate_data_nascimento(self, valor):
        if valor > timezone.localdate():
            raise serializers.ValidationError("A data de nascimento não pode estar no futuro.")
        return valor

    def validate_codigo_v(self, valor):
        if self.instance is not None and valor != self.instance.codigo_v:
            raise serializers.ValidationError("O Código V é permanente e não pode ser alterado.")
        return valor

    def validate_codigo_rm(self, valor):
        return (valor or "").strip() or None

    def validate_distrito(self, valor):
        return (valor or "").strip() or None


class CriancaMonitorSerializer(CriancaSerializer):
    """Versão para monitores: sem telefone."""

    class Meta(CriancaSerializer.Meta):
        fields = CAMPOS_PUBLICOS_CRIANCA


class SalaSerializer(serializers.ModelSerializer):
    profissional_nome = serializers.CharField(source="profissional.nome", read_only=True, default=None)

    class Meta:
        model = Sala
        fields = ["id", "nome", "profissional", "profissional_nome", "ativa"]


class DiaTurmaSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiaTurma
        fields = ["letra", "dia_semana"]


class TurmaSerializer(serializers.ModelSerializer):
    sala_nome = serializers.CharField(source="sala.nome", read_only=True)
    ocupadas = serializers.IntegerField(read_only=True)

    class Meta:
        model = Turma
        fields = ["id", "sala", "sala_nome", "letra", "horario", "tempo", "capacidade", "ano", "ocupadas"]


class MatriculaSerializer(serializers.ModelSerializer):
    crianca_nome = serializers.CharField(source="crianca.nome", read_only=True)

    class Meta:
        model = Matricula
        fields = ["id", "crianca", "crianca_nome", "turma", "data_inicio", "data_fim"]


class RealocacaoSerializer(serializers.ModelSerializer):
    crianca_nome = serializers.CharField(source="crianca.nome", read_only=True)

    class Meta:
        model = Realocacao
        fields = ["id", "crianca", "crianca_nome", "turma_origem", "turma_destino",
                  "data", "realizada_por", "criada_em"]
        read_only_fields = ["realizada_por", "criada_em"]

    def validate(self, attrs):
        # A criança passa o dia na turma de destino, então a data tem de ser o dia dessa turma.
        destino = attrs.get("turma_destino", getattr(self.instance, "turma_destino", None))
        data = attrs.get("data", getattr(self.instance, "data", None))
        if destino is not None and data is not None:
            validar_data_da_turma(destino, data)
        return attrs


class PresencaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Presenca
        fields = ["id", "crianca", "turma", "data", "situacao", "justificativa",
                  "registrado_por", "registrado_em"]
        read_only_fields = ["registrado_por", "registrado_em"]

    def validate_turma(self, turma):
        usuario = self.context["request"].user
        if not turmas_do_usuario(usuario).filter(pk=turma.pk).exists():
            raise serializers.ValidationError("Você não tem acesso a esta turma.")
        return turma

    def validate(self, attrs):
        if self.instance is None:  # na criação, a data tem de ser o dia da turma
            validar_data_da_turma(attrs["turma"], attrs["data"])
        situacao = attrs.get("situacao", getattr(self.instance, "situacao", None))
        justificativa = attrs.get("justificativa", getattr(self.instance, "justificativa", None))
        attrs["justificativa"] = normalizar_justificativa(situacao, justificativa)
        return attrs

    def update(self, instance, validated_data):
        # Criança, turma e data identificam o registro e não mudam.
        for campo in ("crianca", "turma", "data"):
            validated_data.pop(campo, None)
        return super().update(instance, validated_data)


class OcorrenciaSerializer(serializers.ModelSerializer):
    autor_nome = serializers.CharField(source="autor.nome", read_only=True)

    class Meta:
        model = Ocorrencia
        fields = ["id", "crianca", "texto", "categoria", "autor", "autor_nome", "criado_em"]
        read_only_fields = ["autor", "criado_em"]

    def validate_crianca(self, crianca):
        usuario = self.context["request"].user
        if not eh_administrador(usuario) and not criancas_visiveis(usuario).filter(pk=crianca.pk).exists():
            raise serializers.ValidationError("Você não tem acesso a esta criança.")
        return crianca

    def validate_texto(self, valor):
        valor = valor.strip()
        if not valor:
            raise serializers.ValidationError("O texto não pode ficar vazio.")
        return valor

    def validate_categoria(self, valor):
        return (valor or "").strip() or None


class AuditoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Auditoria
        fields = ["id", "usuario_id", "data_hora", "tabela", "registro_id", "acao",
                  "valores_antes", "valores_depois"]


class ChamadaRegistroSerializer(serializers.Serializer):
    crianca = serializers.IntegerField()
    situacao = serializers.ChoiceField(choices=Situacao.choices)
    justificativa = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        attrs["justificativa"] = normalizar_justificativa(attrs["situacao"], attrs.get("justificativa"))
        return attrs


class ChamadaEntradaSerializer(serializers.Serializer):
    data = serializers.DateField()
    registros = ChamadaRegistroSerializer(many=True, allow_empty=False)
