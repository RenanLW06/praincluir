"""Testes automatizados das regras do Vincular (precisam do PostgreSQL ligado).

Rodar:  python manage.py test
Todos os dados abaixo são sintéticos.
"""
import io
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, transaction
from django.test import TestCase
from openpyxl import Workbook
from rest_framework.test import APIClient

from core import planilhas
from core.models import (
    Auditoria, Crianca, DiaTurma, Matricula, Presenca, Realocacao, Sala, Turma, Usuario,
)

SEGUNDA = "2026-12-07"
SEGUNDA_SEGUINTE = "2026-12-14"
TERCA = "2026-12-08"
DOMINGO = "2026-12-06"
INICIO = date(2026, 1, 1)


class BaseApi(TestCase):
    def setUp(self):
        for numero, letra in enumerate("ABCDE", start=1):
            DiaTurma.objects.create(letra=letra, dia_semana=numero)
        self.admin = Usuario.objects.create_user(
            login="admin", password="senha-admin-123", nome="Admin", perfil="administrador")
        self.monitor = Usuario.objects.create_user(
            login="monitor1", password="senha-monitor-123", nome="Monitor", perfil="monitor")
        self.sala = Sala.objects.create(nome="Sala Teste", profissional=self.monitor)
        self.outra_sala = Sala.objects.create(nome="Outra Sala")
        self.a_d1_t1 = self.turma(self.sala, "A", "D1", 1)
        self.admin_api = self.cliente(self.admin)
        self.monitor_api = self.cliente(self.monitor)

    # ---------------------------------------------------------- ajudantes
    @staticmethod
    def cliente(usuario):
        api = APIClient()
        api.force_authenticate(user=usuario)
        return api

    @staticmethod
    def turma(sala, letra, horario, tempo):
        return Turma.objects.create(sala=sala, letra_id=letra, horario=horario, tempo=tempo, ano=2026)

    @staticmethod
    def crianca(numero):
        return Crianca.objects.create(
            nome=f"Crianca {numero}", data_nascimento=date(2016, 1, 1), codigo_v=f"T{numero:03d}",
            responsavel="Responsavel", telefone=f"8800000{numero:04d}")

    @staticmethod
    def matricular(crianca, turma):
        return Matricula.objects.create(crianca=crianca, turma=turma, data_inicio=INICIO)

    def matricular_api(self, crianca, turma):
        return self.admin_api.post(
            "/api/matriculas/",
            {"crianca": crianca.pk, "turma": turma.pk, "data_inicio": "2026-01-01"}, format="json")

    def chamada(self, api, turma, data):
        return api.get(f"/api/turmas/{turma.pk}/chamada/?data={data}")

    def ids_da_chamada(self, resposta):
        return {item["crianca"]: item for item in resposta.json()["criancas"]}


class CadastroTests(BaseApi):
    def test_codigo_v_e_unico_e_imutavel(self):
        c = self.crianca(1)
        corpo = {"nome": "Outra", "data_nascimento": "2016-02-02", "codigo_v": c.codigo_v,
                 "responsavel": "Resp", "telefone": "8811111111"}
        self.assertEqual(self.admin_api.post("/api/criancas/", corpo, format="json").status_code, 400)
        resposta = self.admin_api.patch(f"/api/criancas/{c.pk}/", {"codigo_v": "OUTRO"}, format="json")
        self.assertEqual(resposta.status_code, 400)
        c.refresh_from_db()
        self.assertEqual(c.codigo_v, "T001")

    def test_monitor_nao_ve_telefone_e_so_ve_suas_criancas(self):
        dele, de_fora = self.crianca(1), self.crianca(2)
        self.matricular(dele, self.a_d1_t1)
        resposta = self.monitor_api.get("/api/criancas/")
        self.assertEqual(resposta.status_code, 200)
        itens = resposta.json()["results"]
        self.assertEqual([i["codigo_v"] for i in itens], [dele.codigo_v])
        self.assertNotIn("telefone", itens[0])
        admin = self.admin_api.get("/api/criancas/").json()["results"]
        self.assertEqual(len(admin), 2)
        self.assertIn("telefone", admin[0])
        self.assertIsNotNone(de_fora)

    def test_monitor_nao_cria_crianca(self):
        corpo = {"nome": "X", "data_nascimento": "2016-02-02", "codigo_v": "T999",
                 "responsavel": "R", "telefone": "88"}
        self.assertEqual(self.monitor_api.post("/api/criancas/", corpo, format="json").status_code, 403)


class MatriculaTests(BaseApi):
    def test_capacidade_de_seis(self):
        for n in range(1, 7):
            self.matricular(self.crianca(n), self.a_d1_t1)
        setima = self.crianca(7)
        resposta = self.matricular_api(setima, self.a_d1_t1)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("Turma lotada", str(resposta.json()))

    def test_todas_as_atividades_no_mesmo_horario(self):
        c = self.crianca(1)
        self.matricular(c, self.a_d1_t1)
        a_d2_t1 = self.turma(self.sala, "A", "D2", 1)
        resposta = self.matricular_api(c, a_d2_t1)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("D1/D2", str(resposta.json()))

    def test_todas_as_atividades_no_mesmo_dia(self):
        c = self.crianca(1)
        self.matricular(c, self.a_d1_t1)
        b_d1_t2 = self.turma(self.sala, "B", "D1", 2)
        resposta = self.matricular_api(c, b_d1_t2)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("outro dia da semana", str(resposta.json()))

    def test_duas_atividades_no_dia_uma_em_cada_tempo(self):
        c = self.crianca(1)
        self.matricular(c, self.a_d1_t1)
        a_d1_t2 = self.turma(self.outra_sala, "A", "D1", 2)
        self.assertEqual(self.matricular_api(c, a_d1_t2).status_code, 201)
        # um segundo candidato ao mesmo tempo 1 não pode
        outra_a_d1_t1 = self.turma(self.outra_sala, "A", "D1", 1)
        resposta = self.matricular_api(c, outra_a_d1_t1)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("neste tempo", str(resposta.json()))


class ChamadaTests(BaseApi):
    def test_chamada_recusa_data_fora_do_dia_da_turma(self):
        resposta = self.chamada(self.admin_api, self.a_d1_t1, DOMINGO)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("segundas-feiras", str(resposta.json()))
        self.assertEqual(self.chamada(self.admin_api, self.a_d1_t1, SEGUNDA).status_code, 200)

    def test_justificativa_obrigatoria_so_para_ausencia_justificada(self):
        c = self.crianca(1)
        self.matricular(c, self.a_d1_t1)
        url = f"/api/turmas/{self.a_d1_t1.pk}/chamada/"
        sem = {"data": SEGUNDA, "registros": [{"crianca": c.pk, "situacao": "ausente_justificada"}]}
        self.assertEqual(self.monitor_api.post(url, sem, format="json").status_code, 400)
        com = {"data": SEGUNDA, "registros": [
            {"crianca": c.pk, "situacao": "ausente_justificada", "justificativa": "Consulta"}]}
        self.assertEqual(self.monitor_api.post(url, com, format="json").status_code, 200)
        presenca = Presenca.objects.get(crianca=c, turma=self.a_d1_t1, data=SEGUNDA)
        self.assertEqual(presenca.justificativa, "Consulta")
        # corrigir para presente descarta a justificativa
        presente = {"data": SEGUNDA, "registros": [{"crianca": c.pk, "situacao": "presente"}]}
        self.assertEqual(self.monitor_api.post(url, presente, format="json").status_code, 200)
        presenca.refresh_from_db()
        self.assertEqual(presenca.situacao, "presente")
        self.assertIsNone(presenca.justificativa)

    def test_chamada_recusa_crianca_fora_da_lista(self):
        estranha = self.crianca(9)
        url = f"/api/turmas/{self.a_d1_t1.pk}/chamada/"
        corpo = {"data": SEGUNDA, "registros": [{"crianca": estranha.pk, "situacao": "presente"}]}
        resposta = self.monitor_api.post(url, corpo, format="json")
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("não consta", str(resposta.json()))

    def test_monitor_nao_acessa_turma_de_outra_sala(self):
        alheia = self.turma(self.outra_sala, "A", "D2", 1)
        self.assertEqual(self.chamada(self.monitor_api, alheia, SEGUNDA).status_code, 404)
        self.assertEqual(self.chamada(self.admin_api, alheia, SEGUNDA).status_code, 200)


class RealocacaoTests(BaseApi):
    def test_so_administrador_realoca(self):
        c = self.crianca(1)
        self.matricular(c, self.a_d1_t1)
        destino = self.turma(self.outra_sala, "A", "D1", 1)
        corpo = {"crianca": c.pk, "turma_origem": self.a_d1_t1.pk,
                 "turma_destino": destino.pk, "data": SEGUNDA}
        self.assertEqual(self.monitor_api.post("/api/realocacoes/", corpo, format="json").status_code, 403)
        self.assertEqual(self.admin_api.post("/api/realocacoes/", corpo, format="json").status_code, 201)

    def test_realocacao_vale_so_naquele_dia(self):
        c = self.crianca(1)
        self.matricular(c, self.a_d1_t1)
        destino = self.turma(self.outra_sala, "A", "D1", 1)
        corpo = {"crianca": c.pk, "turma_origem": self.a_d1_t1.pk,
                 "turma_destino": destino.pk, "data": SEGUNDA}
        self.admin_api.post("/api/realocacoes/", corpo, format="json")

        origem_no_dia = self.ids_da_chamada(self.chamada(self.admin_api, self.a_d1_t1, SEGUNDA))
        destino_no_dia = self.ids_da_chamada(self.chamada(self.admin_api, destino, SEGUNDA))
        origem_depois = self.ids_da_chamada(self.chamada(self.admin_api, self.a_d1_t1, SEGUNDA_SEGUINTE))
        self.assertNotIn(c.pk, origem_no_dia)
        self.assertTrue(destino_no_dia[c.pk]["realocada"])
        self.assertIn(c.pk, origem_depois)
        self.assertEqual(Matricula.objects.filter(crianca=c, data_fim__isnull=True).count(), 1)

    def test_data_da_realocacao_deve_ser_o_dia_da_turma_de_destino(self):
        c = self.crianca(1)
        self.matricular(c, self.a_d1_t1)
        b_d1_t1 = self.turma(self.sala, "B", "D1", 1)  # terça
        corpo = {"crianca": c.pk, "turma_origem": self.a_d1_t1.pk, "turma_destino": b_d1_t1.pk}
        errada = self.admin_api.post("/api/realocacoes/", {**corpo, "data": SEGUNDA}, format="json")
        self.assertEqual(errada.status_code, 400)
        certa = self.admin_api.post("/api/realocacoes/", {**corpo, "data": TERCA}, format="json")
        self.assertEqual(certa.status_code, 201)

    def test_realocacao_pode_passar_de_seis(self):
        destino = self.turma(self.outra_sala, "A", "D1", 1)
        for n in range(1, 7):
            self.matricular(self.crianca(n), destino)
        visitante = self.crianca(7)
        self.matricular(visitante, self.a_d1_t1)
        corpo = {"crianca": visitante.pk, "turma_origem": self.a_d1_t1.pk,
                 "turma_destino": destino.pk, "data": SEGUNDA}
        self.assertEqual(self.admin_api.post("/api/realocacoes/", corpo, format="json").status_code, 201)
        lista = self.ids_da_chamada(self.chamada(self.admin_api, destino, SEGUNDA))
        self.assertEqual(len(lista), 7)
        self.assertEqual(Realocacao.objects.count(), 1)


class AuditoriaTests(BaseApi):
    def test_auditoria_registra_quem_fez(self):
        corpo = {"nome": "Auditada", "data_nascimento": "2016-03-03", "codigo_v": "T500",
                 "responsavel": "R", "telefone": "8822222222"}
        resposta = self.admin_api.post("/api/criancas/", corpo, format="json")
        self.assertEqual(resposta.status_code, 201)
        registro = Auditoria.objects.get(tabela="crianca", registro_id=resposta.json()["id"], acao="INSERT")
        self.assertEqual(registro.usuario_id, self.admin.pk)
        self.assertEqual(registro.valores_depois["codigo_v"], "T500")

    def test_auditoria_nao_pode_ser_alterada_nem_apagada(self):
        self.crianca(1)
        self.assertTrue(Auditoria.objects.exists())
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                Auditoria.objects.all().update(acao="DELETE")
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                Auditoria.objects.all().delete()

    def test_apenas_administrador_le_a_auditoria(self):
        self.assertEqual(self.monitor_api.get("/api/auditoria/").status_code, 403)
        self.assertEqual(self.admin_api.get("/api/auditoria/").status_code, 200)

    def test_alteracao_de_presenca_fica_no_historico(self):
        c = self.crianca(1)
        self.matricular(c, self.a_d1_t1)
        url = f"/api/turmas/{self.a_d1_t1.pk}/chamada/"
        self.monitor_api.post(url, {"data": SEGUNDA, "registros": [
            {"crianca": c.pk, "situacao": "presente"}]}, format="json")
        self.admin_api.post(url, {"data": SEGUNDA, "registros": [
            {"crianca": c.pk, "situacao": "ausente"}]}, format="json")
        acoes = list(Auditoria.objects.filter(tabela="presenca").order_by("id").values_list("acao", flat=True))
        self.assertEqual(acoes, ["INSERT", "UPDATE"])


def planilha(linhas):
    wb = Workbook()
    ws = wb.active
    ws.append(["nome", "data_nascimento", "codigo_v", "responsavel", "telefone"])
    for linha in linhas:
        ws.append(linha)
    saida = io.BytesIO()
    wb.save(saida)
    return SimpleUploadedFile("criancas.xlsx", saida.getvalue(), content_type=planilhas.XLSX_MIME)


class ImportacaoTests(BaseApi):
    def enviar(self, linhas, confirmar=False):
        url = "/api/importacao/criancas/" + ("?confirmar=1" if confirmar else "")
        return self.admin_api.post(url, {"arquivo": planilha(linhas)}, format="multipart")

    def test_previa_nao_grava_e_confirmacao_grava(self):
        linhas = [["Ana", "10/03/2015", "T700", "Resp", "8833333333"],
                  ["Bia", "12/04/2016", "T701", "Resp", "8833333334"]]
        previa = self.enviar(linhas)
        self.assertEqual(previa.status_code, 200)
        self.assertFalse(previa.json()["aplicado"])
        self.assertEqual(previa.json()["novas"], 2)
        self.assertEqual(Crianca.objects.count(), 0)
        gravada = self.enviar(linhas, confirmar=True)
        self.assertTrue(gravada.json()["aplicado"])
        self.assertEqual(Crianca.objects.count(), 2)

    def test_com_erro_nada_e_gravado(self):
        linhas = [["Ana", "10/03/2015", "T700", "Resp", "8833333333"],
                  ["Erro", "abc", "T701", "Resp", "8833333334"]]
        resposta = self.enviar(linhas, confirmar=True)
        self.assertFalse(resposta.json()["aplicado"])
        self.assertEqual([e["linha"] for e in resposta.json()["erros"]], [3])
        self.assertEqual(Crianca.objects.count(), 0)

    def test_codigo_v_existente_e_atualizado(self):
        existente = self.crianca(1)
        linhas = [["Novo Nome", "01/01/2016", existente.codigo_v, "Resp Novo", "8844444444"]]
        resposta = self.enviar(linhas, confirmar=True)
        self.assertEqual(resposta.json()["atualizadas"], 1)
        existente.refresh_from_db()
        self.assertEqual(existente.nome, "Novo Nome")
        self.assertEqual(existente.telefone, "8844444444")
        self.assertEqual(Crianca.objects.count(), 1)

    def test_monitor_nao_importa_nem_exporta_cadastro(self):
        self.assertEqual(self.monitor_api.get("/api/exportacao/criancas/").status_code, 403)
        arquivo = {"arquivo": planilha([])}
        self.assertEqual(
            self.monitor_api.post("/api/importacao/criancas/", arquivo, format="multipart").status_code, 403)
