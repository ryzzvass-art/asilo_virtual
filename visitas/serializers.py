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
        # Evitamos el UniqueValidator automático que generaría un mensaje en
        # inglés; lo manejamos manualmente en validate_dni con mensaje propio.
        extra_kwargs = {
            "dni": {"validators": []},
        }

    def get_registrado_por_nombre(self, obj):
        return f"{obj.registrado_por.nombre} {obj.registrado_por.apellido}"

    def validate_dni(self, value):
        """C.I. único entre visitantes. En PATCH excluye la propia instancia."""
        valor = (value or "").strip()
        if not valor:
            raise serializers.ValidationError("El C.I. es obligatorio.")
        qs = Visitante.objects.filter(dni=valor)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "Ya existe un visitante registrado con ese C.I."
            )
        return valor


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
            "visitante_nombre",
            "residente_nombre",
        ]

    def get_visitante_nombre(self, obj):
        return obj.visitante.nombre

    def get_residente_nombre(self, obj):
        r = obj.residente
        return f"{r.nombre} {r.apellido}"

    def get_autorizado_por_nombre(self, obj):
        return f"{obj.autorizado_por.nombre} {obj.autorizado_por.apellido}"


class RegistroVisitaSerializer(serializers.ModelSerializer):
    visitante_nombre      = serializers.SerializerMethodField()
    visitante_dni         = serializers.SerializerMethodField()
    residente_nombre      = serializers.SerializerMethodField()
    residente_dni         = serializers.SerializerMethodField()
    relacion              = serializers.SerializerMethodField()
    registrado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = RegistroVisita
        fields = [
            "id",
            "visitante_residente",
            "visitante_nombre",
            "visitante_dni",
            "residente_nombre",
            "residente_dni",
            "relacion",
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
            "visitante_dni",
            "residente_nombre",
            "residente_dni",
            "relacion",
        ]

    def get_visitante_nombre(self, obj):
        return obj.visitante_residente.visitante.nombre

    def get_visitante_dni(self, obj):
        return obj.visitante_residente.visitante.dni

    def get_residente_nombre(self, obj):
        r = obj.visitante_residente.residente
        return f"{r.nombre} {r.apellido}"

    def get_residente_dni(self, obj):
        return obj.visitante_residente.residente.dni

    def get_relacion(self, obj):
        return obj.visitante_residente.relacion

    def get_registrado_por_nombre(self, obj):
        return f"{obj.registrado_por.nombre} {obj.registrado_por.apellido}"
