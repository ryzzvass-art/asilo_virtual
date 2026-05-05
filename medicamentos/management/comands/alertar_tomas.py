"""
Ejecutar manualmente:
    python manage.py alertar_tomas

Para producción, configurar un cron job que lo ejecute cada minuto:
    * * * * * cd /ruta/proyecto && python manage.py alertar_tomas
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


class Command(BaseCommand):
    help = "Envía alertas WebSocket para tomas en los próximos 30 minutos"

    def handle(self, *args, **options):
        from medicamentos.models import ResidenteMedicamento

        ahora = timezone.now()
        limite = ahora + timedelta(minutes=30)
        channel_layer = get_channel_layer()

        prescripciones = ResidenteMedicamento.objects.filter(
            estado="activo"
        ).select_related("residente", "medicamento")

        alertas_enviadas = 0

        for p in prescripciones:
            for horario in p.horarios:
                hora, minuto = map(int, horario.split(":"))
                hoy_con_hora = ahora.replace(
                    hour=hora, minute=minuto, second=0, microsecond=0
                )
                # T-58: alerta si la toma es en los próximos 30 minutos
                if ahora <= hoy_con_hora <= limite:
                    async_to_sync(channel_layer.group_send)(
                        "notificaciones",
                        {
                            "type": "toma_proxima",
                            "residente": f"{p.residente.nombre} {p.residente.apellido}",
                            "medicamento": p.medicamento.nombre_comercial,
                            "dosis": p.dosis,
                            "hora": horario,
                        },
                    )
                    alertas_enviadas += 1

        self.stdout.write(self.style.SUCCESS(f"✓ {alertas_enviadas} alertas enviadas"))
