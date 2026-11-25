import datetime as dt
import unittest

from core.calendario import erro_dia_da_turma


class CalendarioTests(unittest.TestCase):
    def test_data_no_dia_da_turma_nao_tem_erro(self):
        # 07/12/2026 é segunda-feira; turma A = segunda (1)
        self.assertIsNone(erro_dia_da_turma("A", 1, dt.date(2026, 12, 7)))

    def test_domingo_para_turma_de_segunda(self):
        msg = erro_dia_da_turma("A", 1, dt.date(2026, 12, 6))
        self.assertEqual(
            msg, "A turma A tem aula às segundas-feiras, mas 06/12/2026 é domingo."
        )

    def test_terca_para_turma_de_sexta(self):
        msg = erro_dia_da_turma("E", 5, dt.date(2026, 12, 8))
        self.assertIn("sextas-feiras", msg)
        self.assertIn("terça-feira", msg)

    def test_todas_as_letras_de_segunda_a_sexta(self):
        segunda = dt.date(2026, 12, 7)
        for deslocamento, letra in enumerate("ABCDE"):
            dia = segunda + dt.timedelta(days=deslocamento)
            self.assertIsNone(erro_dia_da_turma(letra, deslocamento + 1, dia))


if __name__ == "__main__":
    unittest.main()
