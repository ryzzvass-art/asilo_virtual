# ============================================================
# SPRINT 2 — T-17, T-18, T-19
# Archivo: residentes/models.py  (reemplaza todo el archivo)
# ============================================================

from django.db import models
from django.conf import settings


class Residente(models.Model):
    """
    Entidad central del sistema. Todo lo demás se conecta a esta tabla.
    Soft delete: estado 'dado_de_alta' en lugar de eliminar físicamente.
    """

    class Estado(models.TextChoices):
        ACTIVO        = "activo",        "Activo"
        HOSPITALIZADO = "hospitalizado", "Hospitalizado"
        DADO_DE_ALTA  = "dado_de_alta",  "Dado de alta"

    nombre          = models.CharField(max_length=100)
    apellido        = models.CharField(max_length=100)
    dni             = models.CharField(max_length=20, unique=True)  # No puede repetirse
    fecha_nacimiento = models.DateField()
    fecha_ingreso   = models.DateField()
    estado          = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.ACTIVO,
    )

    # FK → usuarios.id — quién registró al residente
    # settings.AUTH_USER_MODEL es la forma correcta de referenciar
    # tu modelo Usuario personalizado desde otra app
    registrado_por  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,       # No permite borrar el usuario si tiene residentes
        related_name='residentes_registrados',
        null=True,
        blank=True,
    )

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)   # Se actualiza solo en cada save()

    class Meta:
        db_table = 'residentes'
        indexes = [
            models.Index(fields=['estado'], name='idx_residentes_estado'),
            models.Index(fields=['dni'],    name='idx_residentes_dni'),
        ]

    def __str__(self):
        return f"{self.nombre} {self.apellido} (DNI: {self.dni})"


# ============================================================
# T-18 — Modelo HistorialMedico
# Relación 1:1 con Residente — se crea automáticamente via signal
# ============================================================

class HistorialMedico(models.Model):
    """
    Historial médico del residente.
    Relación OneToOne: un residente tiene exactamente un historial.
    Se crea vacío automáticamente cuando se registra un residente (ver signals.py).
    """

    # OneToOneField = FK con unique=True. Un historial pertenece a UN residente.
    residente = models.OneToOneField(
        Residente,
        on_delete=models.CASCADE,       # Si se borra el residente, se borra el historial
        related_name='historial_medico'
    )

    diagnosticos        = models.TextField(blank=True, default='')
    alergias            = models.TextField(blank=True, default='')
    # condiciones_cronicas alimenta la sugerencia automática de restricciones (RF-22-C, Sprint 6)
    condiciones_cronicas = models.TextField(blank=True, default='')

    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='historiales_actualizados',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'historial_medico'

    def __str__(self):
        return f"Historial de {self.residente}"


# ============================================================
# T-24 — Modelo ContactoEmergencia
# ============================================================

class ContactoEmergencia(models.Model):
    """
    Dos contactos por residente: familiar directo y médico de cabecera.
    El constraint UNIQUE(residente, tipo) garantiza exactamente uno de cada tipo.
    """

    class Tipo(models.TextChoices):
        FAMILIAR        = "familiar",        "Familiar directo"
        MEDICO_CABECERA = "medico_cabecera", "Médico de cabecera"

    residente      = models.ForeignKey(
        Residente,
        on_delete=models.CASCADE,
        related_name='contactos_emergencia'
    )
    tipo           = models.CharField(max_length=20, choices=Tipo.choices)
    nombre         = models.CharField(max_length=150)
    relacion_cargo = models.CharField(max_length=100)
    telefono       = models.CharField(max_length=20)
    email          = models.EmailField(blank=True, default='')

    class Meta:
        db_table = 'contactos_emergencia'
        # Constraint: solo un familiar y un médico por residente
        unique_together = [('residente', 'tipo')]

    def __str__(self):
        return f"{self.tipo} de {self.residente}: {self.nombre}"
