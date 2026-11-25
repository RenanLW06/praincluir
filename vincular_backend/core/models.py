from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Now
from django.utils import timezone


class Perfil(models.TextChoices):
    ADMINISTRADOR = "administrador", "Administrador"
    MONITOR = "monitor", "Monitor"


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, login, password=None, **extra):
        if not login:
            raise ValueError("O login é obrigatório.")
        usuario = self.model(login=login, **extra)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_superuser(self, login, password=None, **extra):
        extra.setdefault("perfil", Perfil.ADMINISTRADOR)
        extra.setdefault("nome", login)
        return self.create_user(login, password, **extra)


class Usuario(AbstractBaseUser):
    nome = models.CharField(max_length=255)
    login = models.CharField(max_length=150, unique=True)
    perfil = models.CharField(max_length=20, choices=Perfil.choices, default=Perfil.MONITOR)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "login"
    REQUIRED_FIELDS = ["nome"]

    objects = UsuarioManager()

    class Meta:
        db_table = "usuario"

    @property
    def is_active(self):
        return self.ativo

    @property
    def eh_administrador(self):
        return self.perfil == Perfil.ADMINISTRADOR

    def __str__(self):
        return self.nome


class Crianca(models.Model):
    nome = models.CharField(max_length=255)
    data_nascimento = models.DateField()
    codigo_v = models.CharField(max_length=50, unique=True)  # único e permanente
    responsavel = models.CharField(max_length=255)
    telefone = models.CharField(max_length=30)
    codigo_rm = models.CharField(max_length=50, null=True, blank=True)
    foto = models.ImageField(upload_to="criancas/", null=True, blank=True)
    distrito = models.CharField(max_length=100, null=True, blank=True)
    ativo = models.BooleanField(default=True)  # desligada = False (nunca apagar)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "crianca"
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.codigo_v})"


class Sala(models.Model):
    nome = models.CharField(max_length=150, unique=True)  # ex.: "Artesania Iara"
    profissional = models.ForeignKey(
        Usuario, null=True, blank=True, on_delete=models.SET_NULL, related_name="salas"
    )
    ativa = models.BooleanField(default=True)

    class Meta:
        db_table = "sala"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class DiaTurma(models.Model):
    """Relaciona a letra da turma (A–E) ao dia da semana (ISO: 1 = segunda)."""

    letra = models.CharField(max_length=1, primary_key=True)
    dia_semana = models.SmallIntegerField(unique=True)

    class Meta:
        db_table = "dia_turma"
        ordering = ["letra"]
        constraints = [
            models.CheckConstraint(condition=Q(letra__in=["A", "B", "C", "D", "E"]), name="ck_dia_turma_letra"),
            models.CheckConstraint(condition=Q(dia_semana__gte=1, dia_semana__lte=7), name="ck_dia_turma_dia"),
        ]

    def __str__(self):
        return self.letra


class Horario(models.TextChoices):
    D1 = "D1", "D1 (13:30–15:30)"
    D2 = "D2", "D2 (15:30–17:30)"


class Turma(models.Model):
    """Sala + letra (dia) + horário (D1/D2) + tempo (1º/2º de 1h)."""

    sala = models.ForeignKey(Sala, on_delete=models.PROTECT, related_name="turmas")
    letra = models.ForeignKey(DiaTurma, on_delete=models.PROTECT, db_column="letra", related_name="turmas")
    horario = models.CharField(max_length=2, choices=Horario.choices)
    tempo = models.SmallIntegerField(choices=[(1, "1º tempo"), (2, "2º tempo")])
    capacidade = models.SmallIntegerField(default=6)
    ano = models.SmallIntegerField()  # período anual

    class Meta:
        db_table = "turma"
        ordering = ["sala__nome", "letra", "horario", "tempo"]
        constraints = [
            models.UniqueConstraint(fields=["sala", "letra", "horario", "tempo", "ano"], name="uq_turma"),
            models.CheckConstraint(condition=Q(capacidade__gt=0), name="ck_turma_capacidade"),
            models.CheckConstraint(condition=Q(horario__in=["D1", "D2"]), name="ck_turma_horario"),
            models.CheckConstraint(condition=Q(tempo__in=[1, 2]), name="ck_turma_tempo"),
        ]

    def __str__(self):
        return f"{self.sala} · {self.letra_id} · {self.horario}/{self.tempo}"


class Matricula(models.Model):
    """Vínculo criança–turma (por atividade). data_fim vazia = matrícula ativa.

    Capacidade, D1/D2 e conflito de horário são validados por gatilhos do banco.
    """

    crianca = models.ForeignKey(Crianca, on_delete=models.PROTECT, related_name="matriculas")
    turma = models.ForeignKey(Turma, on_delete=models.PROTECT, related_name="matriculas")
    data_inicio = models.DateField(default=timezone.localdate)
    data_fim = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "matricula"
        constraints = [
            models.UniqueConstraint(
                fields=["crianca", "turma"], condition=Q(data_fim__isnull=True), name="uq_matricula_ativa"
            ),
            models.CheckConstraint(
                condition=Q(data_fim__isnull=True) | Q(data_fim__gte=F("data_inicio")),
                name="ck_matricula_datas",
            ),
        ]


class Realocacao(models.Model):
    """Realocação de um único dia, feita por administrador; pode exceder a capacidade."""

    crianca = models.ForeignKey(Crianca, on_delete=models.PROTECT, related_name="realocacoes")
    turma_origem = models.ForeignKey(Turma, on_delete=models.PROTECT, related_name="realocacoes_saida")
    turma_destino = models.ForeignKey(Turma, on_delete=models.PROTECT, related_name="realocacoes_entrada")
    data = models.DateField()
    realizada_por = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="+")
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "realocacao"
        constraints = [
            models.CheckConstraint(condition=~Q(turma_origem=F("turma_destino")), name="ck_realocacao_turmas"),
            models.UniqueConstraint(fields=["crianca", "turma_origem", "data"], name="uq_realocacao_dia"),
        ]


class Situacao(models.TextChoices):
    PRESENTE = "presente", "Presente"
    AUSENTE = "ausente", "Ausente"
    AUSENTE_JUSTIFICADA = "ausente_justificada", "Ausente justificada"


class Presenca(models.Model):
    crianca = models.ForeignKey(Crianca, on_delete=models.PROTECT, related_name="presencas")
    turma = models.ForeignKey(Turma, on_delete=models.PROTECT, related_name="presencas")
    data = models.DateField()
    situacao = models.CharField(max_length=20, choices=Situacao.choices)
    justificativa = models.TextField(null=True, blank=True)
    registrado_por = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="+")
    registrado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "presenca"
        indexes = [models.Index(fields=["turma", "data"]), models.Index(fields=["crianca", "data"])]
        constraints = [
            models.UniqueConstraint(fields=["crianca", "turma", "data"], name="uq_presenca"),
            models.CheckConstraint(
                condition=(
                    Q(situacao="ausente_justificada", justificativa__isnull=False) & ~Q(justificativa="")
                )
                | (~Q(situacao="ausente_justificada") & Q(justificativa__isnull=True)),
                name="ck_presenca_justificativa",
            ),
        ]


class Ocorrencia(models.Model):
    crianca = models.ForeignKey(Crianca, on_delete=models.PROTECT, related_name="ocorrencias")
    texto = models.TextField()
    categoria = models.CharField(max_length=100, null=True, blank=True)
    autor = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ocorrencia"
        ordering = ["-criado_em"]
        indexes = [models.Index(fields=["crianca", "-criado_em"])]


class Auditoria(models.Model):
    """Histórico imutável, preenchido apenas por gatilhos do banco."""

    usuario_id = models.BigIntegerField(null=True, blank=True)
    data_hora = models.DateTimeField(db_default=Now())
    tabela = models.CharField(max_length=64)
    registro_id = models.BigIntegerField(null=True, blank=True)
    acao = models.CharField(max_length=10)
    valores_antes = models.JSONField(null=True, blank=True)
    valores_depois = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "auditoria"
        ordering = ["-data_hora", "-id"]
        indexes = [
            models.Index(fields=["tabela", "registro_id", "-data_hora"]),
            models.Index(fields=["usuario_id", "-data_hora"]),
        ]
