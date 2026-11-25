"""Regras de calendário das turmas (sem dependência do Django, fácil de testar).

A letra da turma (A–E) corresponde a um dia da semana. O mapa fica na tabela
`dia_turma` (dia_semana no padrão ISO: 1 = segunda ... 7 = domingo).
"""

NOMES_DIAS = {
    1: "segunda-feira", 2: "terça-feira", 3: "quarta-feira", 4: "quinta-feira",
    5: "sexta-feira", 6: "sábado", 7: "domingo",
}
NOMES_DIAS_PLURAL = {
    1: "segundas-feiras", 2: "terças-feiras", 3: "quartas-feiras", 4: "quintas-feiras",
    5: "sextas-feiras", 6: "sábados", 7: "domingos",
}


def erro_dia_da_turma(letra, dia_esperado, data):
    """Devolve a mensagem de erro se `data` não cai no dia da turma; senão, None."""
    real = data.isoweekday()
    if real == dia_esperado:
        return None
    return (
        f"A turma {letra} tem aula às {NOMES_DIAS_PLURAL[dia_esperado]}, "
        f"mas {data.strftime('%d/%m/%Y')} é {NOMES_DIAS[real]}."
    )
