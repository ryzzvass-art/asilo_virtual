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
        await self.send(
            text_data=json.dumps(
                {
                    "tipo": "tomas_pendientes",
                    "total": len(tomas),
                    "tomas": tomas,
                }
            )
        )

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            if data.get("accion") == "actualizar":
                tomas = await self.get_tomas_pendientes()
                await self.send(
                    text_data=json.dumps(
                        {
                            "tipo": "tomas_pendientes",
                            "total": len(tomas),
                            "tomas": tomas,
                        }
                    )
                )
        except json.JSONDecodeError:
            pass

    @database_sync_to_async
    def get_tomas_pendientes(self):
        from medicamentos.models import (
            ResidenteMedicamento,
            AdministracionMedicamento,
        )

        ahora = timezone.now()  # aware, en UTC
        tz_local = pytz.timezone("America/La_Paz")
        ahora_local = ahora.astimezone(tz_local)
        limite = ahora_local + timedelta(hours=2)

        # Tolerancia para considerar que un registro corresponde a una toma:
        # si el instante programado del registro cae dentro de +/-TOLERANCIA del
        # instante calculado de la toma pendiente, se considera la misma toma.
        # Esto hace el cruce robusto ante diferencias de zona horaria o segundos.
        TOLERANCIA = timedelta(minutes=2)

        tomas = []

        prescripciones = ResidenteMedicamento.objects.filter(
            estado="activo"
        ).select_related("residente", "medicamento")

        # -- Registros de administracion de las ultimas horas -----------------
        # Traemos las administraciones recientes (cualquier estado: administrada
        # u omitida). Una toma que ya tiene registro NO debe seguir pendiente.
        # Guardamos { prescripcion_id: [instante_programado_aware, ...] }.
        desde = ahora - timedelta(hours=6)
        registros = AdministracionMedicamento.objects.filter(
            fecha_hora_programada__gte=desde
        ).values_list("residente_medicamento_id", "fecha_hora_programada")

        registros_por_presc = {}
        for presc_id, fecha_prog in registros:
            if fecha_prog is None:
                continue
            registros_por_presc.setdefault(presc_id, []).append(fecha_prog)

        def ya_registrada(presc_id, instante_toma_aware):
            """True si existe un registro para esa prescripcion cuyo instante
            programado coincide (+/-TOLERANCIA) con el de la toma pendiente."""
            for fecha_prog in registros_por_presc.get(presc_id, []):
                if abs(fecha_prog - instante_toma_aware) <= TOLERANCIA:
                    return True
            return False

        # -- Construir la lista de pendientes ---------------------------------
        for p in prescripciones:
            for horario in p.horarios:
                hora, minuto = map(int, horario.split(":"))
                # Instante de hoy a esa hora, en hora local
                hora_programada_local = ahora_local.replace(
                    hour=hora, minute=minuto, second=0, microsecond=0
                )

                # Solo nos interesan las que caen dentro de las proximas 2 horas
                if not (ahora_local <= hora_programada_local <= limite):
                    continue

                # Instante absoluto (aware) de esta toma, para comparar con los
                # registros sin depender de strings de hora ni de zona.
                instante_toma = hora_programada_local.astimezone(pytz.utc)

                # Si ya hay un registro (administrada u omitida) para esta toma,
                # deja de estar pendiente: la saltamos.
                if ya_registrada(p.pk, instante_toma):
                    continue

                tomas.append(
                    {
                        "prescripcion_id": p.pk,
                        "residente": f"{p.residente.nombre} {p.residente.apellido}",
                        "medicamento": p.medicamento.nombre_comercial,
                        "dosis": p.dosis,
                        "hora_programada": horario,
                        "minutos_restantes": int(
                            (hora_programada_local - ahora_local).total_seconds() / 60
                        ),
                    }
                )

        return sorted(tomas, key=lambda x: x["minutos_restantes"])
