from django.forms.models import model_to_dict
from .models import AuditLog


def get_client_ip(request):
    """Extrae la IP real del cliente considerando proxies."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def serializar_instancia(instancia):
    """Convierte una instancia de modelo a dict serializable como JSON."""
    if instancia is None:
        return None
    try:
        data = {}
        for field in instancia._meta.fields:
            value = getattr(instancia, field.name)
            # Convertir tipos no serializables
            if hasattr(value, "pk"):
                data[field.name] = value.pk
            elif hasattr(value, "isoformat"):
                data[field.name] = value.isoformat()
            else:
                data[field.name] = value
        return data
    except Exception:
        return {"id": getattr(instancia, "pk", None)}


def registrar_auditoria(
    request,
    accion,
    entidad_nombre,
    entidad_id,
    datos_anteriores=None,
    datos_nuevos=None,
):
    """
    Función de servicio para registrar una entrada en el audit log.
    Se puede llamar desde cualquier vista del sistema.
    """
    try:
        AuditLog.objects.create(
            usuario=request.user,
            accion=accion,
            entidad=entidad_nombre,
            entidad_id=entidad_id,
            datos_anteriores=datos_anteriores,
            datos_nuevos=datos_nuevos,
            ip=get_client_ip(request),
        )
    except Exception:
        # El audit log nunca debe interrumpir la operación principal
        pass


class AuditLogMixin:
    """
    T-87: Mixin para vistas DRF.
    Sobrescribe perform_create, perform_update, perform_destroy
    para capturar snapshots y crear AuditLog automáticamente.

    USO — agregar a cualquier APIView o ViewSet:
        class MiView(AuditLogMixin, APIView):
            audit_entidad = 'nombre_tabla'
    """

    audit_entidad = "desconocido"  # Subclases deben definir esto

    def _get_entidad_nombre(self):
        return getattr(self, "audit_entidad", "desconocido")

    def audit_crear(self, request, instancia):
        """Registra creación — datos_anteriores=null."""
        registrar_auditoria(
            request=request,
            accion="crear",
            entidad_nombre=self._get_entidad_nombre(),
            entidad_id=instancia.pk,
            datos_anteriores=None,
            datos_nuevos=serializar_instancia(instancia),
        )

    def audit_editar(self, request, instancia_antes, instancia_despues):
        """Registra edición — snapshot antes y después."""
        registrar_auditoria(
            request=request,
            accion="editar",
            entidad_nombre=self._get_entidad_nombre(),
            entidad_id=instancia_despues.pk,
            datos_anteriores=serializar_instancia(instancia_antes),
            datos_nuevos=serializar_instancia(instancia_despues),
        )

    def audit_archivar(self, request, instancia):
        """Registra archivado/soft delete."""
        registrar_auditoria(
            request=request,
            accion="archivar",
            entidad_nombre=self._get_entidad_nombre(),
            entidad_id=instancia.pk,
            datos_anteriores=None,
            datos_nuevos=serializar_instancia(instancia),
        )
