from rest_framework import serializers
from .models import (
    CatalogoRestriccion,
    CatalogoAlimento,
    AlimentoRestriccion,
    ResidenteRestriccion,
    PlanNutricional,
    ComidaDiaria
)

# ── T-59, T-60 — Catálogo de Restricciones ────────────────


class CatalogoRestriccionSerializer(serializers.ModelSerializer):
    creado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = CatalogoRestriccion
        fields = [
            "id",
            "nombre",
            "descripcion",
            "condiciones_asociadas",
            "severidad",
            "estado",
            "creado_por",
            "creado_por_nombre",
            "created_at",
        ]
        read_only_fields = ["creado_por", "creado_por_nombre", "estado", "created_at"]

    def get_creado_por_nombre(self, obj):
        return f"{obj.creado_por.nombre} {obj.creado_por.apellido}"


# ── T-61, T-62 — Catálogo de Alimentos ────────────────────


class CatalogoAlimentoSerializer(serializers.ModelSerializer):
    """
    Nuevo alimento siempre inicia con estado='pendiente'.
    revisado_por se asigna al activar, no al crear.
    """

    revisado_por_nombre = serializers.SerializerMethodField()
    restricciones_que_viola = serializers.SerializerMethodField()

    class Meta:
        model = CatalogoAlimento
        fields = [
            "id",
            "nombre",
            "grupo_alimentario",
            "estado",
            "revisado_por",
            "revisado_por_nombre",
            "restricciones_que_viola",
            "created_at",
        ]
        read_only_fields = [
            "estado",
            "revisado_por",
            "revisado_por_nombre",
            "restricciones_que_viola",
            "created_at",
        ]

    def get_revisado_por_nombre(self, obj):
        if obj.revisado_por:
            return f"{obj.revisado_por.nombre} {obj.revisado_por.apellido}"
        return None

    def get_restricciones_que_viola(self, obj):
        """Lista de restricciones que viola este alimento."""
        return [
            {
                "id": ar.restriccion.id,
                "nombre": ar.restriccion.nombre,
                "severidad": ar.restriccion.severidad,
            }
            for ar in obj.restricciones_que_viola.select_related("restriccion").all()
        ]


# ── T-63, T-64 — Vinculación Alimento-Restricción ─────────


class AlimentoRestriccionSerializer(serializers.ModelSerializer):
    restriccion_nombre = serializers.SerializerMethodField()
    restriccion_severidad = serializers.SerializerMethodField()

    class Meta:
        model = AlimentoRestriccion
        fields = [
            "alimento",
            "restriccion",
            "restriccion_nombre",
            "restriccion_severidad",
        ]
        read_only_fields = ["restriccion_nombre", "restriccion_severidad"]

    def get_restriccion_nombre(self, obj):
        return obj.restriccion.nombre

    def get_restriccion_severidad(self, obj):
        return obj.restriccion.severidad


# ── T-65, T-66, T-67 — Restricciones del Residente ────────


class ResidenteRestriccionSerializer(serializers.ModelSerializer):
    """
    Para asignar y listar restricciones de un residente.
    confirmado_por se asigna automáticamente con el usuario autenticado.
    """

    restriccion_nombre = serializers.SerializerMethodField()
    restriccion_severidad = serializers.SerializerMethodField()
    confirmado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = ResidenteRestriccion
        fields = [
            "id",
            "residente",
            "restriccion",
            "restriccion_nombre",
            "restriccion_severidad",
            "confirmado_por",
            "confirmado_por_nombre",
            "fecha_activacion",
            "estado",
        ]
        read_only_fields = [
            "confirmado_por",
            "confirmado_por_nombre",
            "fecha_activacion",
            "residente",
        ]

    def get_restriccion_nombre(self, obj):
        return obj.restriccion.nombre

    def get_restriccion_severidad(self, obj):
        return obj.restriccion.severidad

    def get_confirmado_por_nombre(self, obj):
        return f"{obj.confirmado_por.nombre} {obj.confirmado_por.apellido}"


class AsignarRestriccionSerializer(serializers.Serializer):
    """
    T-67: Para asignar restricción con confirmación explícita.
    Si la restricción es obligatoria, confirmado debe ser True.
    """

    restriccion_id = serializers.IntegerField()
    confirmado = serializers.BooleanField(default=False)

    def validate(self, data):
        from .models import CatalogoRestriccion

        try:
            restriccion = CatalogoRestriccion.objects.get(
                pk=data["restriccion_id"], estado="activo"
            )
        except CatalogoRestriccion.DoesNotExist:
            raise serializers.ValidationError(
                {"restriccion_id": "Restricción no encontrada o archivada."}
            )

        # T-67: restricción obligatoria requiere confirmado=True
        if restriccion.severidad == "obligatorio" and not data.get("confirmado"):
            raise serializers.ValidationError(
                {
                    "confirmado": (
                        f"La restricción '{restriccion.nombre}' es OBLIGATORIA. "
                        "Debe enviar confirmado=true para activarla."
                    )
                }
            )

        data["restriccion"] = restriccion
        return data
# ── T-68, T-69 — Planes Nutricionales ─────────────────────

class PlanNutricionalSerializer(serializers.ModelSerializer):
    """
    Para crear y listar planes.
    creado_por y residente se asignan automáticamente en la vista.
    """
    creado_por_nombre = serializers.SerializerMethodField()
 
    class Meta:
        model  = PlanNutricional
        fields = [
            'id', 'residente', 'tipo_dieta', 'observaciones',
            'fecha_inicio', 'fecha_fin', 'estado',
            'creado_por', 'creado_por_nombre', 'created_at',
        ]
        read_only_fields = [
            'residente', 'creado_por', 'creado_por_nombre',
            'estado', 'created_at',
        ]
 
    def get_creado_por_nombre(self, obj):
        return f"{obj.creado_por.nombre} {obj.creado_por.apellido}"
 
 
# ── T-70, T-71, T-72 — Comidas Diarias ────────────────────
 
class ComidaDiariaSerializer(serializers.ModelSerializer):
    """
    Para registrar y listar comidas de un plan.
    Valida que el alimento esté activo antes de guardar.
    La verificación de restricciones se hace en la vista (T-73, T-74).
    """
    alimento_nombre   = serializers.SerializerMethodField()
    registrado_por_nombre = serializers.SerializerMethodField()
 
    class Meta:
        model  = ComidaDiaria
        fields = [
            'id', 'plan', 'fecha', 'tipo_comida',
            'alimento', 'alimento_nombre',
            'descripcion_menu',
            'registrado_por', 'registrado_por_nombre',
        ]
        read_only_fields = [
            'plan', 'registrado_por', 'registrado_por_nombre',
            'alimento_nombre',
        ]
 
    def get_alimento_nombre(self, obj):
        return obj.alimento.nombre
 
    def get_registrado_por_nombre(self, obj):
        return f"{obj.registrado_por.nombre} {obj.registrado_por.apellido}"
 
    def validate_alimento(self, value):
        """T-71: Alimento archivado o pendiente devuelve 400."""
        if value.estado != 'activo':
            raise serializers.ValidationError(
                f"El alimento '{value.nombre}' no está activo "
                f"(estado actual: {value.estado}). Solo se pueden asignar alimentos activos."
            )
        return value
