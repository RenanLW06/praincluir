from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("usuarios", views.UsuarioViewSet, basename="usuario")
router.register("criancas", views.CriancaViewSet, basename="crianca")
router.register("salas", views.SalaViewSet, basename="sala")
router.register("dias-turma", views.DiaTurmaViewSet, basename="dia-turma")
router.register("turmas", views.TurmaViewSet, basename="turma")
router.register("matriculas", views.MatriculaViewSet, basename="matricula")
router.register("realocacoes", views.RealocacaoViewSet, basename="realocacao")
router.register("presencas", views.PresencaViewSet, basename="presenca")
router.register("ocorrencias", views.OcorrenciaViewSet, basename="ocorrencia")
router.register("auditoria", views.AuditoriaViewSet, basename="auditoria")

urlpatterns = [
    path("auth/login/", views.LoginView.as_view()),
    path("auth/logout/", views.LogoutView.as_view()),
    path("auth/eu/", views.EuView.as_view()),
    path("importacao/criancas/", views.ImportacaoCriancasView.as_view()),
    path("importacao/criancas/modelo/", views.ModeloImportacaoCriancasView.as_view()),
    path("exportacao/criancas/", views.ExportacaoCriancasView.as_view()),
    path("exportacao/presencas/", views.ExportacaoPresencasView.as_view()),
    path("", include(router.urls)),
]
