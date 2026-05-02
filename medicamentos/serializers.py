

from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from .models import CatalogoMedicamento, StockMedicamento


# ── T-40 — Catálogo de medicamentos ───────────────────────

class CatalogoMedicamentoSerializer(serializers.ModelSerializer):
    """
    Para crear y listar medicamentos.
    creado_por se asigna automáticamente en la vista.
    """
    creado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model  = CatalogoMedicamento
        fields = [
            'id', 'nombre_comercial', 'principio_activo', 'tipo',
            'forma_farmaceutica', 'contraindicaciones', 'estado',
            'creado_por', 'creado_por_nombre', 'created_at',
        ]
        read_only_fields = ['creado_por', 'creado_por_nombre', 'estado', 'created_at']

    def get_creado_por_nombre(self, obj):
        return f"{obj.creado_por.nombre} {obj.creado_por.apellido}"


class CatalogoMedicamentoEditarSerializer(serializers.ModelSerializer):
    """Para editar medicamentos — no permite cambiar estado desde aquí."""
    class Meta:
        model  = CatalogoMedicamento
        fields = [
            'nombre_comercial', 'principio_activo', 'tipo',
            'forma_farmaceutica', 'contraindicaciones',
        ]


# ── T-43, T-44 — Stock por lote ────────────────────────────

class StockMedicamentoSerializer(serializers.ModelSerializer):
    """
    Para crear y listar lotes de stock.
    Valida que fecha_vencimiento sea futura (T-44).
    """
    actualizado_por_nombre = serializers.SerializerMethodField()
    alerta                 = serializers.SerializerMethodField()

    class Meta:
        model  = StockMedicamento
        fields = [
            'id', 'cantidad', 'unidad', 'fecha_vencimiento',
            'umbral_minimo', 'lote',
            'actualizado_por', 'actualizado_por_nombre',
            'updated_at', 'alerta',
        ]
        read_only_fields = ['actualizado_por', 'actualizado_por_nombre', 'updated_at', 'alerta']

    def get_actualizado_por_nombre(self, obj):
        return f"{obj.actualizado_por.nombre} {obj.actualizado_por.apellido}"

    def get_alerta(self, obj):
        """Indica si este lote tiene alguna alerta activa."""
        hoy      = timezone.now().date()
        alertas  = []
        if obj.cantidad <= obj.umbral_minimo:
            alertas.append("stock_bajo")
        if obj.fecha_vencimiento <= hoy + timedelta(days=30):
            alertas.append("vencimiento_proximo")
        return alertas

    def validate_fecha_vencimiento(self, value):
        """T-44: Lote con fecha_vencimiento pasada devuelve 400."""
        if value <= timezone.now().date():
            raise serializers.ValidationError(
                "La fecha de vencimiento debe ser futura."
            )
        return value

    def validate_cantidad(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "La cantidad no puede ser negativa."
            )
        return value
