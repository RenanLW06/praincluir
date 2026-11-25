from rest_framework.response import Response
from rest_framework.views import exception_handler, set_rollback
from django.db import DatabaseError

MENSAGENS_POR_RESTRICAO = {
    "codigo_v": "Já existe uma criança com este Código V.",
    "uq_matricula_ativa": "A criança já está matriculada nesta turma.",
    "uq_presenca": "A presença desta criança nesta turma e data já foi registrada.",
    "uq_realocacao_dia": "Esta criança já foi realocada desta turma nesta data.",
    "uq_turma": "Já existe uma turma com esta sala, letra, horário, tempo e ano.",
}


def _sqlstate(original):
    return getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)


def tratar_excecoes(exc, context):
    """Converte erros das regras do banco (gatilhos e restrições) em respostas 400."""
    resposta = exception_handler(exc, context)
    if resposta is not None:
        return resposta

    if isinstance(exc, DatabaseError):
        original = exc.__cause__
        estado = _sqlstate(original)
        diag = getattr(original, "diag", None)

        if estado == "P0001":  # RAISE EXCEPTION dos gatilhos
            set_rollback()
            mensagem = getattr(diag, "message_primary", None) or "Operação não permitida."
            return Response({"detail": mensagem}, status=400)

        if estado and estado.startswith("23"):  # violação de integridade
            set_rollback()
            restricao = getattr(diag, "constraint_name", None) or ""
            for trecho, mensagem in MENSAGENS_POR_RESTRICAO.items():
                if trecho in restricao:
                    return Response({"detail": mensagem}, status=400)
            return Response({"detail": "Os dados enviados violam uma regra do banco de dados."}, status=400)

        if estado and estado.startswith("22"):  # dado inválido
            set_rollback()
            return Response({"detail": "Valor inválido enviado."}, status=400)

    return None
