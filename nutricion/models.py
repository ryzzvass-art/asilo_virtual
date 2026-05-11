from django.db import models
from django.conf import settings


class CatalogoRestriccion(models.Model):
    """
    Catálogo de restricciones alimentarias.
    Solo el Administrador lo gestiona.
    severidad='obligatorio' bloquea con confirmación explícita.
    severidad='recomendado' genera advertencia.
    """

    class Severidad(models.TextChoices):
        OBLIGATORIO = "obligatorio", "Obligatorio"
        RECOMENDADO = "recomendado", "Recomendado"

    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        ARCHIVADO = "archivado", "Archivado"

    nombre = models.CharField(max_length=150)  # sin azúcar, bajo en sodio, etc.
    descripcion = models.TextField(blank=True, default="")
    condiciones_asociadas = models.CharField(
        max_length=255, blank=True, default=""
    )  # Diabetes, Hipertensión, etc.
    severidad = models.CharField(max_length=20, choices=Severidad.choices)
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.ACTIVO
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="restricciones_creadas",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "catalogo_restricciones"
        indexes = [
            models.Index(fields=["estado"], name="idx_restricciones_estado"),
            models.Index(fields=["severidad"], name="idx_restricciones_severidad"),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.severidad})"


class CatalogoAlimento(models.Model):
    """
    Catálogo de alimentos disponibles para los menús.
    Nuevo alimento inicia con estado='pendiente'.
    Solo activos aparecen en los menús.
    Solo el Admin puede activar un alimento (revisado_por).
    """

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente de revisión"
        ACTIVO = "activo", "Activo"
        ARCHIVADO = "archivado", "Archivado"

    nombre = models.CharField(max_length=200)
    grupo_alimentario = models.CharField(
        max_length=100
    )  # cereal, proteína, lácteo, vegetal, postre, etc.
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE,  # Siempre inicia pendiente
    )
    # null=True porque al crear aún no tiene revisor
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alimentos_revisados",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "catalogo_alimentos"
        indexes = [
            models.Index(fields=["estado"], name="idx_alimentos_estado"),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.grupo_alimentario})"


class AlimentoRestriccion(models.Model):
    """
    Tabla N:M — qué restricciones viola cada alimento.
    Corazón de la verificación RF-25.
    PK compuesta (alimento_id, restriccion_id). Sin campos adicionales.
    """

    alimento = models.ForeignKey(
        CatalogoAlimento,
        on_delete=models.CASCADE,
        related_name="restricciones_que_viola",
    )
    restriccion = models.ForeignKey(
        CatalogoRestriccion,
        on_delete=models.CASCADE,
        related_name="alimentos_afectados",
    )

    class Meta:
        db_table = "alimento_restricciones"
        unique_together = [("alimento", "restriccion")]  # PK compuesta

    def __str__(self):
        return f"{self.alimento} viola → {self.restriccion}"


class ResidenteRestriccion(models.Model):
    """
    Restricciones activas de cada residente.
    NINGUNA se activa sin confirmación humana explícita (RF-22-C).
    confirmado_por no puede ser null.
    """

    class Estado(models.TextChoices):
        ACTIVA = "activa", "Activa"
        REVOCADA = "revocada", "Revocada"

    residente = models.ForeignKey(
        "residentes.Residente",
        on_delete=models.CASCADE,
        related_name="restricciones_alimentarias",
    )
    restriccion = models.ForeignKey(
        CatalogoRestriccion,
        on_delete=models.CASCADE,
        related_name="residentes_con_restriccion",
    )
    # confirmado_por nunca puede ser null — regla de negocio RF-22-C
    confirmado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="restricciones_confirmadas",
    )
    fecha_activacion = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.ACTIVA
    )

    class Meta:
        db_table = "residente_restricciones"
        unique_together = [
            ("residente", "restriccion")
        ]  # Una restricción por residente

    def __str__(self):
        return f"{self.residente} — {self.restriccion} ({self.estado})"


# SPRINT 7 — T-68, T-70
class PlanNutricional(models.Model):
    """
    Plan nutricional con versionado — solo uno vigente por residente.
    Al crear plan nuevo, el anterior se archiva automáticamente (RF-26).
    """

    class Estado(models.TextChoices):
        VIGENTE = "vigente", "Vigente"
        ARCHIVADO = "archivado", "Archivado"

    class TipoDieta(models.TextChoices):
        BLANDA = "blanda", "Blanda"
        HIPOCALORICA = "hipocalorica", "Hipocalórica"
        NORMAL = "normal", "Normal"
        DIABETICA = "diabetica", "Diabética"
        HIPOSODICA = "hiposodica", "Hiposódica"
        OTRO = "otro", "Otro"

    residente = models.ForeignKey(
        "residentes.Residente",
        on_delete=models.CASCADE,
        related_name="planes_nutricionales",
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="planes_creados",
    )
    tipo_dieta = models.CharField(max_length=20, choices=TipoDieta.choices)
    observaciones = models.TextField(blank=True, default="")
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)  # null = plan vigente
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.VIGENTE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "planes_nutricionales"
        ordering = ["-fecha_inicio"]

    def __str__(self):
        return f"Plan {self.tipo_dieta} — {self.residente} ({self.estado})"


class ComidaDiaria(models.Model):
    """
    Comidas asignadas por día en un plan nutricional.
    Al guardar se verifica RF-25: alimento vs restricciones activas del residente.
    """

    class TipoComida(models.TextChoices):
        DESAYUNO = "desayuno", "Desayuno"
        ALMUERZO = "almuerzo", "Almuerzo"
        MERIENDA = "merienda", "Merienda"
        CENA = "cena", "Cena"

    plan = models.ForeignKey(
        PlanNutricional, on_delete=models.CASCADE, related_name="comidas"
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="comidas_registradas",
    )
    fecha = models.DateField()
    tipo_comida = models.CharField(max_length=20, choices=TipoComida.choices)
    alimento = models.ForeignKey(
        CatalogoAlimento, on_delete=models.PROTECT, related_name="en_comidas"
    )
    descripcion_menu = models.TextField(blank=True, default="")

    class Meta:
        db_table = "comidas_diarias"
        ordering = ["fecha", "tipo_comida"]

    def __str__(self):
        return f"{self.tipo_comida} del {self.fecha} — {self.alimento}"
