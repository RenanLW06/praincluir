from pathlib import Path

from django.apps import AppConfig
from django.db import connections
from django.db.models.signals import post_migrate

TABELAS_NECESSARIAS = {
    "usuario", "crianca", "sala", "dia_turma", "turma", "matricula",
    "realocacao", "presenca", "ocorrencia", "auditoria",
}


def aplicar_regras_do_banco(sender, using="default", **kwargs):
    """Cria/atualiza funções e gatilhos (capacidade, realocação, presença, auditoria).

    O script é idempotente e roda ao final de todo `migrate`.
    """
    conexao = connections[using]
    if conexao.vendor != "postgresql":
        return
    if not TABELAS_NECESSARIAS.issubset(set(conexao.introspection.table_names())):
        return
    sql = (Path(__file__).parent / "sql" / "regras_banco.sql").read_text(encoding="utf-8")
    with conexao.cursor() as cursor:
        cursor.execute(sql)


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        post_migrate.connect(aplicar_regras_do_banco, sender=self)
