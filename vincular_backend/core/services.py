from django.db import connection
from django.db.models import Q
from rest_framework.exceptions import ValidationError

from .calendario import erro_dia_da_turma
from .models import Crianca, Turma
from .permissions import eh_administrador


def turmas_do_usuario(usuario):
    """Administrador vê todas as turmas; monitor, só as das suas salas."""
    turmas = Turma.objects.all()
    if eh_administrador(usuario):
        return turmas
    return turmas.filter(sala__profissional=usuario)


def criancas_visiveis(usuario):
    """Monitor vê as crianças matriculadas (ou realocadas) nas suas turmas."""
    if eh_administrador(usuario):
        return Crianca.objects.all()
    return Crianca.objects.filter(
        Q(matriculas__data_fim__isnull=True, matriculas__turma__sala__profissional=usuario)
        | Q(realocacoes__turma_destino__sala__profissional=usuario)
    ).distinct()


def lista_chamada(turma_id, data):
    """Crianças que devem constar na chamada da turma nesta data (usa fn_lista_chamada)."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT crianca_id, nome, codigo_v, realocada FROM fn_lista_chamada(%s, %s)",
            [turma_id, data],
        )
        return [
            {"crianca": linha[0], "nome": linha[1], "codigo_v": linha[2], "realocada": linha[3]}
            for linha in cursor.fetchall()
        ]


def validar_data_da_turma(turma, data, campo="data"):
    """Recusa datas que não caem no dia da semana da turma (A = segunda ... E = sexta)."""
    mensagem = erro_dia_da_turma(turma.letra_id, turma.letra.dia_semana, data)
    if mensagem:
        raise ValidationError({campo: [mensagem]})
