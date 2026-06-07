from django.db import models
from django.conf import settings


class CatalogoRestriccion(models.Model):
    class Severidad(models.TextChoices):
        OBLIGATORIO = "obligatorio", "Obligatorio"
        RECOMENDADO = "recomendado", "Recomendado"

    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        ARCHIVADO = "archivado", "Archivado"

    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, default="")
    condiciones_asociadas = models.CharField(max_length=255, blank=True, default="")
    severidad = models.CharField(max_length=20, choices=Severidad.choices)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ACTIVO)
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
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente de revisión"
        ACTIVO = "activo", "Activo"
        ARCHIVADO = "archivado", "Archivado"

    nombre = models.CharField(max_length=200)
    grupo_alimentario = models.CharField(max_length=100)
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
    )
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
       ordering = ["-created_at"]
       indexes = [
        models.Index(fields=["estado"], name="idx_alimentos_estado"),
    ]
    def __str__(self):
        return f"{self.nombre} ({self.grupo_alimentario})"


class AlimentoRestriccion(models.Model):
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
        unique_together = [("alimento", "restriccion")]

    def __str__(self):
        return f"{self.alimento} viola → {self.restriccion}"


class ResidenteRestriccion(models.Model):
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
        unique_together = [("residente", "restriccion")]

    def __str__(self):
        return f"{self.residente} — {self.restriccion} ({self.estado})"


# ── NUEVO: Plantilla Nutricional reutilizable ──────────────


class PlantillaNutricional(models.Model):
    """
    Plantilla reutilizable de plan nutricional.
    No está atada a ningún residente.
    Flujo: pendiente → aprobado / rechazado.
    La crea cualquier usuario (Admin o Cuidador).
    Solo el Admin aprueba o rechaza.
    """

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente de aprobación"
        APROBADO = "aprobado", "Aprobado"
        RECHAZADO = "rechazado", "Rechazado"

    class TipoDieta(models.TextChoices):
        BLANDA = "blanda", "Blanda"
        HIPOCALORICA = "hipocalorica", "Hipocalórica"
        NORMAL = "normal", "Normal"
        DIABETICA = "diabetica", "Diabética"
        HIPOSODICA = "hiposodica", "Hiposódica"
        OTRO = "otro", "Otro"

    nombre = models.CharField(max_length=200)
    tipo_dieta = models.CharField(max_length=20, choices=TipoDieta.choices)
    observaciones = models.TextField(blank=True, default="")
    fecha_menu = models.DateField()
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
    )

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="plantillas_creadas",
    )
    # Solo se rellena al aprobar o rechazar
    aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="plantillas_aprobadas",
    )
    motivo_rechazo = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "plantillas_nutricionales"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["estado"], name="idx_plantillas_estado"),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.tipo_dieta}) — {self.estado}"


class ComidaPlantilla(models.Model):
    """
    Comidas base que forman parte de una PlantillaNutricional.
    No tienen fecha ni residente — son la definición genérica.
    Al asignar la plantilla a un residente, estas comidas
    se COPIAN a ComidaDiaria del plan asignado.
    """

    class TipoComida(models.TextChoices):
        DESAYUNO = "desayuno", "Desayuno"
        ALMUERZO = "almuerzo", "Almuerzo"
        MERIENDA = "merienda", "Merienda"
        CENA = "cena", "Cena"

    plantilla = models.ForeignKey(
        PlantillaNutricional,
        on_delete=models.CASCADE,
        related_name="comidas",
    )
    tipo_comida = models.CharField(max_length=20, choices=TipoComida.choices)
    alimento = models.ForeignKey(
        CatalogoAlimento,
        on_delete=models.PROTECT,
        related_name="en_plantillas",
    )
    descripcion_menu = models.TextField(blank=True, default="")

    class Meta:
        db_table = "comidas_plantilla"
        ordering = ["tipo_comida"]

    def __str__(self):
        return f"{self.tipo_comida} — {self.alimento} (plantilla: {self.plantilla.nombre})"


# ── Plan Nutricional asignado a residente (evolución) ─────


class PlanNutricional(models.Model):
    """
    Plan nutricional asignado a un residente específico.
    Puede originarse de una PlantillaNutricional aprobada
    (plantilla_origen) o crearse directamente (legacy / null).

    Estados:
    - vigente:   plan activo del residente
    - archivado: reemplazado por uno más nuevo
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
    # Nullable: planes legacy (creados antes de este cambio) no tienen plantilla origen
    plantilla_origen = models.ForeignKey(
        PlantillaNutricional,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planes_asignados",
    )
    tipo_dieta = models.CharField(max_length=20, choices=TipoDieta.choices)
    observaciones = models.TextField(blank=True, default="")
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
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
    Comidas asignadas por día en un plan nutricional de un residente.
    Pueden venir copiadas de una ComidaPlantilla (al asignar)
    o agregadas manualmente después.
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