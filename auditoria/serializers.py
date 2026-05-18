from rest_framework import serializers
from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "usuario",
            "usuario_nombre",
            "accion",
            "entidad",
            "entidad_id",
            "datos_anteriores",
            "datos_nuevos",
            "ip",
            "fecha_hora",
        ]

    def get_usuario_nombre(self, obj):
        return f"{obj.usuario.nombre} {obj.usuario.apellido}"
