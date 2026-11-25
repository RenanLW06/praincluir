from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Perfil


def eh_administrador(usuario):
    return bool(usuario and usuario.is_authenticated and usuario.perfil == Perfil.ADMINISTRADOR)


class EhAdministrador(BasePermission):
    message = "Apenas administradores podem realizar esta ação."

    def has_permission(self, request, view):
        return eh_administrador(request.user)


class AdminEscreveDemaisLeem(BasePermission):
    """Qualquer usuário autenticado lê; só administrador altera."""

    message = "Apenas administradores podem alterar estes dados."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return eh_administrador(request.user)
