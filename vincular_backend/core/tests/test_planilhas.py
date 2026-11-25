import datetime as dt
import io
import unittest

from openpyxl import Workbook

from core import planilhas


def xlsx(linhas):
    wb = Workbook()
    ws = wb.active
    for linha in linhas:
        ws.append(linha)
    saida = io.BytesIO()
    wb.save(saida)
    saida.seek(0)
    return saida


CABECALHO = ["Nome", "Data de Nascimento", "Código V", "Nome do responsável",
             "Telefone para contato", "Código RM"]


class PlanilhaTests(unittest.TestCase):
    def test_cabecalhos_com_acento_e_apelidos(self):
        arq = xlsx([CABECALHO, ["Maria", dt.date(2016, 5, 20), "V1", "Ana", 88999999999, None]])
        registros, erros = planilhas.validar_linhas(planilhas.ler_linhas(arq), hoje=dt.date(2026, 11, 16))
        self.assertEqual(erros, [])
        self.assertEqual(registros[0]["telefone"], "88999999999")
        self.assertEqual(registros[0]["codigo_rm"], None)
        self.assertEqual(registros[0]["data_nascimento"], dt.date(2016, 5, 20))

    def test_data_em_texto_brasileiro(self):
        arq = xlsx([CABECALHO, ["Maria", "20/05/2016", "V1", "Ana", "8899", None]])
        registros, erros = planilhas.validar_linhas(planilhas.ler_linhas(arq))
        self.assertEqual(erros, [])
        self.assertEqual(registros[0]["data_nascimento"], dt.date(2016, 5, 20))

    def test_erros_por_linha(self):
        arq = xlsx([
            CABECALHO,
            ["Maria", dt.date(2016, 5, 20), "V1", "Ana", "8899", None],
            ["Pedro", "data errada", "V2", "Rui", "8898", None],
            ["Joana", dt.date(2017, 1, 1), "V1", "Rui", "8897", None],   # Código V repetido
            [None, dt.date(2017, 1, 1), "V3", "Rui", "8897", None],      # nome vazio
            ["Futuro", dt.date(2030, 1, 1), "V4", "Rui", "8897", None],  # nascimento no futuro
        ])
        registros, erros = planilhas.validar_linhas(planilhas.ler_linhas(arq), hoje=dt.date(2026, 11, 16))
        self.assertEqual(len(registros), 1)
        self.assertEqual([e["linha"] for e in erros], [3, 4, 5, 6])

    def test_coluna_obrigatoria_ausente(self):
        arq = xlsx([["Nome", "Telefone"], ["Maria", "88"]])
        with self.assertRaises(planilhas.ErroPlanilha):
            planilhas.ler_linhas(arq)

    def test_arquivo_invalido(self):
        with self.assertRaises(planilhas.ErroPlanilha):
            planilhas.ler_linhas(io.BytesIO(b"isto nao e uma planilha"))

    def test_linhas_vazias_sao_ignoradas(self):
        arq = xlsx([CABECALHO, [None] * 6, ["Maria", dt.date(2016, 5, 20), "V1", "Ana", "8899", None]])
        self.assertEqual(len(planilhas.ler_linhas(arq)), 1)

    def test_modelo_e_exportacao_geram_xlsx(self):
        conteudo = planilhas.modelo_importacao_criancas()
        registros, erros = planilhas.validar_linhas(planilhas.ler_linhas(io.BytesIO(conteudo)))
        self.assertEqual(erros, [])
        self.assertEqual(registros[0]["codigo_v"], "V0001")


if __name__ == "__main__":
    unittest.main()
