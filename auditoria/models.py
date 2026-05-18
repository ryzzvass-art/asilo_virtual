from django.db import models
from django.conf import settings


class AuditLog(models.Model):
    """
    Log de auditoría automático — registra toda acción relevante del sistema.
    RF-30, RF-31.
    Sin FK directas a otras tablas — referencia genérica via entidad+entidad_id.
    Solo consultable por rol administrador.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="acciones_auditadas",
    )
    accion = models.CharField(max_length=50)  # crear, editar, archivar, activar, etc.
    entidad = models.CharField(max_length=100)  # Nombre de la tabla afectada
    entidad_id = models.IntegerField()  # ID del registro afectado
    datos_anteriores = models.JSONField(
        null=True, blank=True
    )  # Snapshot antes del cambio
    datos_nuevos = models.JSONField(
        null=True, blank=True
    )  # Snapshot después del cambio
    ip = models.CharField(max_length=50, blank=True, default="")
    fecha_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_log"
        ordering = ["-fecha_hora"]
        indexes = [
            models.Index(fields=["entidad"], name="idx_audit_entidad"),
            models.Index(fields=["accion"], name="idx_audit_accion"),
            models.Index(fields=["fecha_hora"], name="idx_audit_fecha"),
            models.Index(fields=["usuario"], name="idx_audit_usuario"),
        ]

    def __str__(self):
        return f"{self.accion} en {self.entidad}#{self.entidad_id} por {self.usuario}"
