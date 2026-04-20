from rest_framework.permissions import BasePermission


class IsAdministrador(BasePermission):
    """
    Permite acceso solo a usuarios con rol 'administrador'.
    """
    message = "Solo los administradores pueden realizar esta acción."

    def has_permission(self, request, view):
        # Verificar que el usuario está autenticado
        # y que su rol es administrador
        return (
            request.user.is_authenticated and
            request.user.rol == "administrador"
        )


class IsCuidador(BasePermission):
    """
    Permite acceso solo a usuarios con rol 'cuidador'.
    """
    message = "Solo los cuidadores pueden realizar esta acción."

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.rol == "cuidador"
        )


class IsAdminOrCuidador(BasePermission):
    """
    Permite acceso a administradores y cuidadores.
    Básicamente cualquier usuario autenticado con rol válido.
    """
    message = "Debe estar autenticado para realizar esta acción."

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.rol in ["administrador", "cuidador"]
        )