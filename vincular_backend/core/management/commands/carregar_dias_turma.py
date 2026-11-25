from django.core.management.base import BaseCommand, CommandError

from core.models import DiaTurma


class Command(BaseCommand):
    help = "Define qual dia da semana corresponde a cada letra de turma (ISO: 1 = segunda)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--mapa", default="A=1,B=2,C=3,D=4,E=5",
            help="Ex.: A=1,B=2,C=3,D=4,E=5 (confirme a regra real antes de usar)",
        )

    def handle(self, *args, **opcoes):
        try:
            pares = [item.split("=") for item in opcoes["mapa"].split(",")]
            mapa = {letra.strip().upper(): int(dia) for letra, dia in pares}
        except ValueError:
            raise CommandError("Formato inválido. Use, por exemplo: A=1,B=2,C=3,D=4,E=5")
        for letra, dia in mapa.items():
            DiaTurma.objects.update_or_create(letra=letra, defaults={"dia_semana": dia})
            self.stdout.write(f"{letra} -> dia {dia}")
