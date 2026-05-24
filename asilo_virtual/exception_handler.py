from rest_framework.views import exception_handler
from rest_framework.response import Response


def custom_exception_handler(exc, context):
    """
    Handler global que estandariza todos los errores del sistema.
    Formato: {"error": string, "detalle": string|object, "codigo": int}
    """
    response = exception_handler(exc, context)

    if response is not None:
        codigo = response.status_code

        if codigo == 400:
            error = "Solicitud inválida"
        elif codigo == 401:
            error = "No autenticado"
        elif codigo == 403:
            error = "Acceso denegado"
        elif codigo == 404:
            error = "Recurso no encontrado"
        elif codigo == 405:
            error = "Método no permitido"
        else:
            error = "Error del servidor"

        response.data = {
            "error":   error,
            "detalle": response.data,
            "codigo":  codigo,
        }

    return response