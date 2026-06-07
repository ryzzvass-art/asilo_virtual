from django.db import models
from django.conf import settings


class Actividad(models.Model):
    """
    Actividades y eventos del asilo.
    Cancelada = archivado lógico. Aparece en alertas del dashboard (RF-28).
    """

    class Tipo(models.TextChoices):
        TALLER = "taller", "Taller"
        FISIOTERAPIA = "fisioterapia", "Fisioterapia"
        CUMPLEANOS = "cumpleanos", "Cumpleaños"
        RECREATIVA = "recreativa", "Recreativa"
        DEPORTIVO = "deportivo", "Deportivo"
        OTRO = "otro", "Otro"

    class Estado(models.TextChoices):
        PROGRAMADA = "programada", "Programada"
        REALIZADA = "realizada", "Realizada"
        CANCELADA = "cancelada", "Cancelada"

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="actividades_creadas",
    )
    nombre = models.CharField(max_length=200)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    tipo_otro = models.CharField(max_length=100, blank=True, default="")
    responsable = models.CharField(max_length=150)  
    fecha_hora = models.DateTimeField()
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.PROGRAMADA
    )
    observaciones = models.TextField(blank=True, default="")


    class Meta:
        db_table = "actividades"
        ordering = ["fecha_hora"]
        indexes = [
            models.Index(fields=["estado"], name="idx_actividades_estado"),
            models.Index(fields=["fecha_hora"], name="idx_actividades_fecha"),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.tipo}) — {self.fecha_hora:%Y-%m-%d %H:%M}"


class ActividadResidente(models.Model):
    """
    Tabla N:M — participantes de cada actividad.
    PK compuesta (actividad, residente).
    """

    actividad = models.ForeignKey(
        Actividad, on_delete=models.CASCADE, related_name="participantes"
    )
    residente = models.ForeignKey(
        "residentes.Residente",
        on_delete=models.CASCADE,
        related_name="actividades_asignadas",
    )
    asignado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="asignaciones_actividad",
    )
    fecha_asignacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "actividad_residentes"
        unique_together = [("actividad", "residente")]  # PK compuesta

    def __str__(self):
        return f"{self.residente} en {self.actividad}"
