from rest_framework.permissions import BasePermission


class IsAdministrador(BasePermission):
    """
    Permite acceso solo a usuarios con rol 'administrador'.
    """

    message = "Solo los administradores pueden realizar esta acción."

    def has_permission(self, request, view):
        # Verificar que el usuario está autenticado
        # y que su rol es administrador
        return request.user.is_authenticated and request.user.rol == "administrador"


class IsCuidador(BasePermission):
    """
    Permite acceso solo a usuarios con rol 'cuidador'.
    """

    message = "Solo los cuidadores pueden realizar esta acción."

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol == "cuidador"


class IsAdminOrCuidador(BasePermission):
    """
    Permite acceso a administradores y cuidadores.
    Básicamente cualquier usuario autenticado con rol válido.
    """

    message = "Debe estar autenticado para realizar esta acción."

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol in [
            "administrador",
            "cuidador",
        ]
class PuedeEditarUsuario(BasePermission):
    """
    Reglas de edición de usuarios:
    - Un administrador puede editar SUS PROPIOS datos (y solo los suyos
      entre los administradores).
    - Un administrador puede editar los datos de CUALQUIER cuidador.
    - Un cuidador no puede editar a nadie.

    Nota: la restricción de "no tocar el password de un cuidador" NO se
    decide aquí (esto solo dice sí/no al registro completo). Eso se maneja
    en el serializer/vista, porque es una regla sobre un CAMPO, no sobre
    el permiso de editar el registro.
    """

    message = "No tienes permiso para editar este usuario."

    def has_permission(self, request, view):
        # Puerta de entrada: solo administradores autenticados pueden
        # siquiera intentar editar. (Los cuidadores quedan fuera aquí.)
        return request.user.is_authenticated and request.user.rol == "administrador"

    def has_object_permission(self, request, view, obj):
        # 'obj' es el Usuario que se quiere editar.
        editor = request.user

        # Caso 1: se está editando a sí mismo → permitido.
        if obj.pk == editor.pk:
            return True

        # Caso 2: el objetivo es un cuidador → permitido.
        if obj.rol == "cuidador":
            return True

        # Caso 3: el objetivo es OTRO administrador → prohibido.
        return False
