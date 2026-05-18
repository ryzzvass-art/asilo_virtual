from rest_framework import serializers
from .models import Visitante, VisitanteResidente, RegistroVisita


class VisitanteSerializer(serializers.ModelSerializer):
    registrado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Visitante
        fields = [
            "id",
            "nombre",
            "dni",
            "telefono",
            "registrado_por",
            "registrado_por_nombre",
            "created_at",
        ]
        read_only_fields = ["registrado_por", "registrado_por_nombre", "created_at"]

    def get_registrado_por_nombre(self, obj):
        return f"{obj.registrado_por.nombre} {obj.registrado_por.apellido}"


class VisitanteResidenteSerializer(serializers.ModelSerializer):
    visitante_nombre = serializers.SerializerMethodField()
    residente_nombre = serializers.SerializerMethodField()
    autorizado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = VisitanteResidente
        fields = [
            "id",
            "visitante",
            "visitante_nombre",
            "residente",
            "residente_nombre",
            "relacion",
            "estado",
            "autorizado_por",
            "autorizado_por_nombre",
            "fecha_autorizacion",
        ]
        read_only_fields = [
            "autorizado_por",
            "autorizado_por_nombre",
            "fecha_autorizacion",
        ]

    def get_visitante_nombre(self, obj):
        return obj.visitante.nombre

    def get_residente_nombre(self, obj):
        return f"{obj.residente.nombre} {obj.residente.apellido}"

    def get_autorizado_por_nombre(self, obj):
        return f"{obj.autorizado_por.nombre} {obj.autorizado_por.apellido}"


class RegistroVisitaSerializer(serializers.ModelSerializer):
    visitante_nombre = serializers.SerializerMethodField()
    residente_nombre = serializers.SerializerMethodField()
    registrado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = RegistroVisita
        fields = [
            "id",
            "visitante_residente",
            "visitante_nombre",
            "residente_nombre",
            "registrado_por",
            "registrado_por_nombre",
            "fecha_hora_entrada",
            "fecha_hora_salida",
            "estado",
            "observaciones",
        ]
        read_only_fields = [
            "registrado_por",
            "registrado_por_nombre",
            "fecha_hora_entrada",
            "estado",
            "visitante_nombre",
            "residente_nombre",
        ]

    def get_visitante_nombre(self, obj):
        return obj.visitante_residente.visitante.nombre

    def get_residente_nombre(self, obj):
        r = obj.visitante_residente.residente
        return f"{r.nombre} {r.apellido}"

    def get_registrado_por_nombre(self, obj):
        return f"{obj.registrado_por.nombre} {obj.registrado_por.apellido}"
