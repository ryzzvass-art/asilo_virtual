from rest_framework import serializers
from .models import Actividad, ActividadResidente


class ActividadSerializer(serializers.ModelSerializer):
    creado_por_nombre = serializers.SerializerMethodField()
    total_participantes = serializers.SerializerMethodField()

    class Meta:
        model = Actividad
        fields = [
            "id",
            "nombre",
            "tipo",
            "tipo_otro",
            "responsable",
            "fecha_hora",
            "estado",
            "observaciones",
            "creado_por",
            "creado_por_nombre",
            "total_participantes",
        ]
        read_only_fields = [
            "creado_por",
            "creado_por_nombre",
            "estado",
            "observaciones",
            "total_participantes",
        ]

    def get_creado_por_nombre(self, obj):
        return f"{obj.creado_por.nombre} {obj.creado_por.apellido}"

    def get_total_participantes(self, obj):
        return obj.participantes.count()

    def validate(self, data):
        # Si el tipo es "otro", tipo_otro es obligatorio
        tipo = data.get("tipo", getattr(self.instance, "tipo", None))
        tipo_otro = data.get("tipo_otro", getattr(self.instance, "tipo_otro", ""))
        if tipo == "otro" and not (tipo_otro or "").strip():
            raise serializers.ValidationError(
                {"tipo_otro": "Debe especificar el tipo de actividad."}
            )
        # Si el tipo NO es "otro", limpiamos tipo_otro para no dejar basura
        if tipo != "otro":
            data["tipo_otro"] = ""
        return data


class ActividadResidenteSerializer(serializers.ModelSerializer):
    residente_nombre = serializers.SerializerMethodField()
    asignado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = ActividadResidente
        fields = [
            "actividad",
            "residente",
            "residente_nombre",
            "asignado_por",
            "asignado_por_nombre",
            "fecha_asignacion",
        ]
        read_only_fields = [
            "actividad",
            "asignado_por",
            "asignado_por_nombre",
            "fecha_asignacion",
        ]

    def get_residente_nombre(self, obj):
        return f"{obj.residente.nombre} {obj.residente.apellido}"

    def get_asignado_por_nombre(self, obj):
        return f"{obj.asignado_por.nombre} {obj.asignado_por.apellido}"
