from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from .models import (
    CatalogoMedicamento,
    StockMedicamento,
    ResidenteMedicamento,
    AdministracionMedicamento,
)

# ── T-40 — Catálogo de medicamentos ───────────────────────


class CatalogoMedicamentoSerializer(serializers.ModelSerializer):
    """
    Para crear y listar medicamentos.
    creado_por se asigna automáticamente en la vista.
    """

    creado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = CatalogoMedicamento
        fields = [
            "id",
            "nombre_comercial",
            "principio_activo",
            "tipo",
            "forma_farmaceutica",
            "contraindicaciones",
            "observaciones",
            "estado",
            "creado_por",
            "creado_por_nombre",
            "created_at",
        ]
        read_only_fields = ["creado_por", "creado_por_nombre", "estado", "created_at","observaciones",]

    def get_creado_por_nombre(self, obj):
        return f"{obj.creado_por.nombre} {obj.creado_por.apellido}"


class CatalogoMedicamentoEditarSerializer(serializers.ModelSerializer):
    """Para editar medicamentos — no permite cambiar estado desde aquí."""

    class Meta:
        model = CatalogoMedicamento
        fields = [
            "nombre_comercial",
            "principio_activo",
            "tipo",
            "forma_farmaceutica",
            "contraindicaciones",
            "observaciones",
        ]


# ── T-43, T-44 — Stock por lote ────────────────────────────


class StockMedicamentoSerializer(serializers.ModelSerializer):
    """
    Para crear y listar lotes de stock.
    Valida que fecha_vencimiento sea futura (T-44).
    """

    actualizado_por_nombre = serializers.SerializerMethodField()
    alerta = serializers.SerializerMethodField()
    tiene_administraciones = serializers.SerializerMethodField()
    unidad = serializers.SerializerMethodField()          # ← Añadido

    class Meta:
        model = StockMedicamento
        fields = [
            "id",
            "cantidad",
            "unidad",
            "fecha_vencimiento",
            "umbral_minimo",
            "lote",
            "observaciones",                    # ← Añadido
            "tiene_administraciones",
            "actualizado_por",
            "actualizado_por_nombre",
            "updated_at",
            "alerta",
        ]
        read_only_fields = [
            "actualizado_por",
            "actualizado_por_nombre",
            "updated_at",
            "alerta",
            "unidad",                           # Ahora es de solo lectura
        ]

    def get_actualizado_por_nombre(self, obj):
        return f"{obj.actualizado_por.nombre} {obj.actualizado_por.apellido}"

    def get_alerta(self, obj):
        """Indica si este lote tiene alguna alerta activa."""
        hoy = timezone.now().date()
        alertas = []
        if obj.cantidad <= obj.umbral_minimo:
            alertas.append("stock_bajo")
        if obj.fecha_vencimiento <= hoy + timedelta(days=30):
            alertas.append("vencimiento_proximo")
        return alertas

    def get_tiene_administraciones(self, obj):
        return obj.movimientos.filter(
            tipo="salida", administracion__isnull=False
        ).exists()

    def get_unidad(self, obj):
        # La unidad SIEMPRE refleja la forma farmacéutica actual del medicamento
        # (corrección 1: editar el medicamento actualiza la unidad de todos sus lotes).
        return obj.medicamento.forma_farmaceutica

    def validate_fecha_vencimiento(self, value):
        """T-44: Lote con fecha_vencimiento pasada devuelve 400."""
        if value <= timezone.now().date():
            raise serializers.ValidationError(
                "La fecha de vencimiento debe ser futura."
            )
        return value

    def validate_cantidad(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "La cantidad debe ser mayor a 0 para registrar un lote."
            )
        return value


# Resto de serializers sin cambios...
class ResidenteMedicamentoSerializer(serializers.ModelSerializer):
    """
    Para crear y listar prescripciones.
    Valida que el medicamento exista y esté activo en el catálogo (T-49).
    """

    prescrito_por_nombre = serializers.SerializerMethodField()
    medicamento_nombre = serializers.SerializerMethodField()
    num_administraciones = serializers.SerializerMethodField()
    medicamento_estado = serializers.SerializerMethodField()

    class Meta:
        model = ResidenteMedicamento
        fields = [
            "id",
            "residente",
            "medicamento",
            "medicamento_nombre",
            "prescrito_por",
            "prescrito_por_nombre",
            "dosis",
            "via_administracion",
            "horarios",
            "fecha_inicio",
            "fecha_fin",
            "estado",
            "num_administraciones",
            "medicamento_estado",
            "created_at",
        ]
        read_only_fields = [
            "residente",
            "prescrito_por",
            "prescrito_por_nombre",
            "medicamento_nombre",
            "estado",
            "created_at",
        ]

    def get_prescrito_por_nombre(self, obj):
        return f"{obj.prescrito_por.nombre} {obj.prescrito_por.apellido}"

    def get_medicamento_nombre(self, obj):
        return obj.medicamento.nombre_comercial
    
    def get_num_administraciones(self, obj):
        return obj.administraciones.count()

    def get_medicamento_estado(self, obj):
        return obj.medicamento.estado

    def validate_medicamento(self, value):
        """T-49: medicamento archivado devuelve 400."""
        if value.estado == "archivado":
            raise serializers.ValidationError(
                "No se puede prescribir un medicamento archivado."
            )
        return value

    def validate_horarios(self, value):
        """Valida que horarios sea una lista de strings HH:MM."""
        if not isinstance(value, list) or len(value) == 0:
            raise serializers.ValidationError(
                "Horarios debe ser una lista con al menos un horario. Ej: ['08:00','20:00']"
            )
        import re

        for h in value:
            if not re.match(r"^\d{2}:\d{2}$", h):
                raise serializers.ValidationError(
                    f"Horario '{h}' inválido. Formato esperado: HH:MM"
                )
        return value


class PrescripcionFinalizarSerializer(serializers.Serializer):
    """Para finalizar una prescripción activa."""

    fecha_fin = serializers.DateField(required=False)


class AdministracionMedicamentoSerializer(serializers.ModelSerializer):
    """
    Para registrar y consultar tomas.
    Si administrado=False, observacion es obligatoria (T-52).
    """

    realizado_por_nombre = serializers.SerializerMethodField()
    residente_nombre = serializers.SerializerMethodField()
    medicamento_nombre = serializers.SerializerMethodField()   # ← Añadido

    class Meta:
        model = AdministracionMedicamento
        fields = [
            "id",
            "residente_medicamento",
            "realizado_por",
            "realizado_por_nombre",
            "residente_nombre",
            "medicamento_nombre",                    
            "administrado",
            "fecha_hora_programada",
            "fecha_hora_real",
            "observacion",
            "corregida",
        ]
        read_only_fields = [
            "realizado_por", 
            "realizado_por_nombre", 
            "residente_nombre",
            "medicamento_nombre",
            "corregida"                    
        ]

    def get_realizado_por_nombre(self, obj):
        return f"{obj.realizado_por.nombre} {obj.realizado_por.apellido}"

    def get_residente_nombre(self, obj):
        r = obj.residente_medicamento.residente
        return f"{r.nombre} {r.apellido}"

    def get_medicamento_nombre(self, obj):
        return obj.residente_medicamento.medicamento.nombre_comercial   # ← Añadido

    def validate(self, data):
        """T-52: administrado=False sin observacion devuelve 400."""
        if (
            not data.get("administrado", True)
            and not data.get("observacion", "").strip()
        ):
            raise serializers.ValidationError(
                {
                    "observacion": "La observación es obligatoria cuando el medicamento no fue administrado."
                }
            )
        return data


class AdministracionResumenSerializer(serializers.Serializer):
    """
    T-55: Resumen de administraciones en un período.
    """

    total_programadas = serializers.IntegerField()
    total_administradas = serializers.IntegerField()
    total_omitidas = serializers.IntegerField()


class MovimientoStockSerializer(serializers.ModelSerializer):
    """
    Para listar movimientos de stock de un medicamento (historial de trazabilidad).
    """

    realizado_por_nombre = serializers.SerializerMethodField()
    lote_nombre = serializers.SerializerMethodField()
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        from .models import MovimientoStock
        model = MovimientoStock
        fields = [
            "id",
            "tipo",
            "tipo_display",
            "cantidad",
            "motivo",
            "lote",
            "lote_nombre",
            "realizado_por_nombre",
            "created_at",
        ]

    def get_realizado_por_nombre(self, obj):
        return f"{obj.realizado_por.nombre} {obj.realizado_por.apellido}"

    def get_lote_nombre(self, obj):
        return obj.lote.lote if obj.lote else "—"