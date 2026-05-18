from django.db import models
from django.conf import settings


class Visitante(models.Model):
    """
    Personas externas registradas como visitantes del asilo.
    Un visitante NO es un usuario del sistema. No tiene login.
    Puede estar autorizado para visitar a más de un residente.
    """

    nombre = models.CharField(max_length=150)
    dni = models.CharField(max_length=20)
    telefono = models.CharField(max_length=20)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="visitantes_registrados",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "visitantes"

    def __str__(self):
        return f"{self.nombre} (DNI: {self.dni})"


class VisitanteResidente(models.Model):
    """
    Autorización de un visitante para visitar a un residente específico.
    UNIQUE(visitante, residente) — un visitante puede ser familiar de un
    residente y amigo de otro, con relaciones distintas.
    """

    class Relacion(models.TextChoices):
        FAMILIAR = "familiar", "Familiar"
        AMIGO = "amigo", "Amigo"
        REPRESENTANTE_LEGAL = "representante_legal", "Representante legal"
        OTRO = "otro", "Otro"

    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        SUSPENDIDO = "suspendido", "Suspendido"

    visitante = models.ForeignKey(
        Visitante, on_delete=models.CASCADE, related_name="autorizaciones"
    )
    residente = models.ForeignKey(
        "residentes.Residente",
        on_delete=models.CASCADE,
        related_name="visitantes_autorizados",
    )
    relacion = models.CharField(max_length=20, choices=Relacion.choices)
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.ACTIVO
    )
    autorizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="autorizaciones_visita",
    )
    fecha_autorizacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "visitante_residente"
        unique_together = [("visitante", "residente")]

    def __str__(self):
        return f"{self.visitante} → {self.residente} ({self.relacion})"


class RegistroVisita(models.Model):
    """
    Registro de cada visita real: entrada y salida al asilo.
    El residente se obtiene via: registros_visita → visitante_residente → residente_id
    No hay FK directa al residente.
    """

    class Estado(models.TextChoices):
        EN_CURSO = "en_curso", "En curso"
        FINALIZADA = "finalizada", "Finalizada"
        PENDIENTE_CIERRE = "pendiente_cierre", "Pendiente de cierre"

    visitante_residente = models.ForeignKey(
        VisitanteResidente, on_delete=models.PROTECT, related_name="registros"
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="visitas_registradas",
    )
    fecha_hora_entrada = models.DateTimeField(auto_now_add=True)  # Automática al crear
    fecha_hora_salida = models.DateTimeField(
        null=True, blank=True
    )  # null hasta registrar salida
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.EN_CURSO
    )
    observaciones = models.TextField(blank=True, default="")

    class Meta:
        db_table = "registros_visita"
        ordering = ["-fecha_hora_entrada"]

    def __str__(self):
        return f"Visita de {self.visitante_residente.visitante} — {self.fecha_hora_entrada:%Y-%m-%d %H:%M}"
