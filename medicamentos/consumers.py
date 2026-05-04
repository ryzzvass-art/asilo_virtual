import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from datetime import timedelta
import pytz


class TomaPendienteConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        await self.accept()
        tomas = await self.get_tomas_pendientes()
        await self.send(text_data=json.dumps({
            "tipo":  "tomas_pendientes",
            "total": len(tomas),
            "tomas": tomas,
        }))

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            if data.get("accion") == "actualizar":
                tomas = await self.get_tomas_pendientes()
                await self.send(text_data=json.dumps({
                    "tipo":  "tomas_pendientes",
                    "total": len(tomas),
                    "tomas": tomas,
                }))
        except json.JSONDecodeError:
            pass

    @database_sync_to_async
    def get_tomas_pendientes(self):          # ← la función
        from medicamentos.models import ResidenteMedicamento   # ← indentado adentro

        ahora       = timezone.now()
        tz_local    = pytz.timezone('America/La_Paz')
        ahora_local = ahora.astimezone(tz_local)
        limite      = ahora_local + timedelta(hours=2)
        tomas       = []

        prescripciones = ResidenteMedicamento.objects.filter(
            estado="activo"
        ).select_related("residente", "medicamento")

        for p in prescripciones:
            for horario in p.horarios:
                hora, minuto = map(int, horario.split(":"))
                hoy_local = ahora_local.replace(
                    hour=hora, minute=minuto, second=0, microsecond=0
                )
                if ahora_local <= hoy_local <= limite:
                    tomas.append({
                        "prescripcion_id":   p.pk,
                        "residente":         f"{p.residente.nombre} {p.residente.apellido}",
                        "medicamento":       p.medicamento.nombre_comercial,
                        "dosis":             p.dosis,
                        "hora_programada":   horario,
                        "minutos_restantes": int((hoy_local - ahora_local).total_seconds() / 60),
                    })

        return sorted(tomas, key=lambda x: x["minutos_restantes"])