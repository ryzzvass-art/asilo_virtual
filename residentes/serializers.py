# ============================================================
# SPRINT 2 — Serializers
# Archivo NUEVO: residentes/serializers.py
# ============================================================

from rest_framework import serializers
from .models import Residente, HistorialMedico, ContactoEmergencia
from .models import ObservacionDiaria, TurnoMedico
              


# ============================================================
# T-17, T-19 — Serializer de Residente
# ============================================================

class ContactoEmergenciaSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ContactoEmergencia
        fields = ['id', 'tipo', 'nombre', 'relacion_cargo', 'telefono', 'email']


class ResidenteSerializer(serializers.ModelSerializer):
    """
    Serializer principal de Residente.
    - Para crear: acepta los campos básicos
    - Para leer: incluye datos del registrador (nombre completo)
    """

    # Campo de solo lectura — muestra nombre completo del usuario que registró
    registrado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model  = Residente
        fields = [
            'id', 'nombre', 'apellido', 'dni',
            'fecha_nacimiento', 'fecha_ingreso', 'estado',
            'registrado_por', 'registrado_por_nombre',
            'created_at', 'updated_at',
        ]
        # registrado_por se asigna automáticamente en la vista, no lo envía el cliente
        read_only_fields = ['registrado_por', 'registrado_por_nombre', 'created_at', 'updated_at']

    def get_registrado_por_nombre(self, obj):
        if obj.registrado_por:
            return f"{obj.registrado_por.nombre} {obj.registrado_por.apellido}"
        return None


class ResidenteDetalleSerializer(serializers.ModelSerializer):
    """
    Serializer para el detalle completo del residente (T-21, RF-09).
    Incluye contactos de emergencia e historial médico anidados.
    """
    contactos_emergencia = ContactoEmergenciaSerializer(many=True, read_only=True)
    registrado_por_nombre = serializers.SerializerMethodField()

    # Historial médico anidado
    historial = serializers.SerializerMethodField()

    class Meta:
        model  = Residente
        fields = [
            'id', 'nombre', 'apellido', 'dni',
            'fecha_nacimiento', 'fecha_ingreso', 'estado',
            'registrado_por', 'registrado_por_nombre',
            'contactos_emergencia', 'historial',
            'created_at', 'updated_at',
        ]

    def get_registrado_por_nombre(self, obj):
        if obj.registrado_por:
            return f"{obj.registrado_por.nombre} {obj.registrado_por.apellido}"
        return None

    def get_historial(self, obj):
        try:
            h = obj.historial_medico
            return {
                'id': h.id,
                'diagnosticos': h.diagnosticos,
                'alergias': h.alergias,
                'condiciones_cronicas': h.condiciones_cronicas,
                'updated_at': h.updated_at,
            }
        except HistorialMedico.DoesNotExist:
            return None


# ============================================================
# T-22, T-23 — Serializer para editar residente
# ============================================================

class ResidenteEditarSerializer(serializers.ModelSerializer):
    """
    Para edición parcial o total. No permite cambiar el DNI
    una vez registrado (campo protegido).
    """
    class Meta:
        model  = Residente
        fields = ['nombre', 'apellido', 'fecha_nacimiento', 'fecha_ingreso']


class CambiarEstadoResidenteSerializer(serializers.Serializer):
    estado = serializers.ChoiceField(
        choices=Residente.Estado.choices
    )


# ============================================================
# T-24, T-25 — Serializer de ContactoEmergencia
# ============================================================

class ContactoEmergenciaCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ContactoEmergencia
        fields = ['tipo', 'nombre', 'relacion_cargo', 'telefono', 'email']

    def validate_tipo(self, value):
        # Verificar que el tipo sea válido
        tipos_validos = [t[0] for t in ContactoEmergencia.Tipo.choices]
        if value not in tipos_validos:
            raise serializers.ValidationError(
                f"Tipo inválido. Opciones: {tipos_validos}"
            )
        return value


# ============================================================
# T-26, T-27 — Serializer de HistorialMedico
# ============================================================

class HistorialMedicoSerializer(serializers.ModelSerializer):
    """
    Para ver y editar el historial médico del residente.
    actualizado_por se asigna automáticamente en la vista.
    """
    actualizado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model  = HistorialMedico
        fields = [
            'id', 'diagnosticos', 'alergias', 'condiciones_cronicas',
            'actualizado_por', 'actualizado_por_nombre',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['actualizado_por', 'actualizado_por_nombre', 'created_at', 'updated_at']

    def get_actualizado_por_nombre(self, obj):
        if obj.actualizado_por:
            return f"{obj.actualizado_por.nombre} {obj.actualizado_por.apellido}"
        return None
    
# ── T-30, T-32, T-33 — Observaciones ──────────────────────

class ObservacionDiariaSerializer(serializers.ModelSerializer):
    """
    Para crear y listar observaciones.
    fecha_hora y registrado_por son de solo lectura — se asignan automáticamente.
    registrado_por_nombre: nombre completo del cuidador sin exponer el ID.
    """
    registrado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model  = ObservacionDiaria
        fields = [
            'id', 'estado_fisico', 'estado_emocional',
            'registrado_por', 'registrado_por_nombre', 'fecha_hora',
        ]
        read_only_fields = ['registrado_por', 'registrado_por_nombre', 'fecha_hora']

    def get_registrado_por_nombre(self, obj):
        # T-33: datos denormalizados del registrador para no hacer segunda consulta
        return f"{obj.registrado_por.nombre} {obj.registrado_por.apellido}"


# ── T-35, T-36, T-37, T-38 — Turnos médicos ───────────────

class TurnoMedicoSerializer(serializers.ModelSerializer):
    """
    Para crear y listar turnos médicos.
    tipo_consulta valida que solo acepte los 3 valores definidos en choices.
    """
    registrado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model  = TurnoMedico
        fields = [
            'id', 'tipo_consulta', 'observaciones', 'fecha_hora',
            'registrado_por', 'registrado_por_nombre',
        ]
        read_only_fields = ['registrado_por', 'registrado_por_nombre']

    def get_registrado_por_nombre(self, obj):
        return f"{obj.registrado_por.nombre} {obj.registrado_por.apellido}"

    def validate_tipo_consulta(self, value):
        # T-37: valor inválido devuelve 400
        tipos_validos = [t[0] for t in TurnoMedico.TipoConsulta.choices]
        if value not in tipos_validos:
            raise serializers.ValidationError(
                f"Tipo inválido. Opciones: {tipos_validos}"
            )
        return value
