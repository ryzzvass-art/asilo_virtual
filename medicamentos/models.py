# SPRINT 4 — T-39, T-42


from django.db import models
from django.conf import settings


class CatalogoMedicamento(models.Model):
    """
    Catálogo centralizado de fármacos.
    Solo el Administrador lo gestiona.
    Soft delete: estado 'archivado' en lugar de eliminar.
    Archivados no aparecen en nuevas asignaciones.
    """

    class Estado(models.TextChoices):
        ACTIVO    = "activo",    "Activo"
        ARCHIVADO = "archivado", "Archivado"

    nombre_comercial   = models.CharField(max_length=200)
    principio_activo   = models.CharField(max_length=200)
    tipo               = models.CharField(max_length=100)   # Categoría terapéutica
    forma_farmaceutica = models.CharField(max_length=100)   # comprimido, jarabe, inyectable, etc.
    contraindicaciones = models.TextField(blank=True, default='')
    estado             = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.ACTIVO,
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='medicamentos_creados'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'catalogo_medicamentos'
        indexes = [
            models.Index(fields=['estado'],          name='idx_medicamentos_estado'),
            models.Index(fields=['nombre_comercial'], name='idx_medicamentos_nombre'),
        ]

    def __str__(self):
        return f"{self.nombre_comercial} ({self.principio_activo})"


class StockMedicamento(models.Model):
    """
    Control de stock por lote.
    Un medicamento puede tener múltiples lotes con distintos vencimientos.
    Genera alerta si cantidad <= umbral_minimo O fecha_vencimiento <= hoy+30 días.
    """

    medicamento = models.ForeignKey(
        CatalogoMedicamento,
        on_delete=models.CASCADE,
        related_name='lotes'
    )
    cantidad          = models.IntegerField()
    unidad            = models.CharField(max_length=50)    # comprimidos, ml, frascos, etc.
    fecha_vencimiento = models.DateField()
    umbral_minimo     = models.IntegerField(default=10)    # Alerta si cantidad <= este valor
    lote              = models.CharField(max_length=100)   # Número de lote del proveedor

    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='stocks_actualizados'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'stock_medicamentos'

    def __str__(self):
        return f"Lote {self.lote} — {self.medicamento} ({self.cantidad} {self.unidad})"
