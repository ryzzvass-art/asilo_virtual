from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from auditoria.mixins import AuditLogMixin,serializar_instancia

from .models import Visitante, VisitanteResidente, RegistroVisita
from .serializers import (
    VisitanteSerializer,
    VisitanteResidenteSerializer,
    RegistroVisitaSerializer,
)
from usuarios.permissions import IsAdministrador, IsAdminOrCuidador
from residentes.models import Residente

# ── T-82, T-83 — Visitantes y Autorizaciones ──────────────


class VisitanteListCreateView(APIView):
    """
    GET  /api/visitantes/  → listar visitantes (filtro ?nombre= y ?dni=)
    POST /api/visitantes/  → registrar visitante (solo Admin)
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdministrador()]
        return [IsAdminOrCuidador()]

    def get(self, request):
        nombre = request.query_params.get("nombre")
        dni    = request.query_params.get("dni")
        queryset = Visitante.objects.all().select_related("registrado_por")
        if nombre:
            queryset = queryset.filter(nombre__icontains=nombre)
        if dni:
            queryset = queryset.filter(dni__icontains=dni)
        serializer = VisitanteSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = VisitanteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save(registrado_por=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class VisitanteAutorizacionesView(APIView):
    """
    GET /api/visitantes/{id}/autorizaciones/
    Lista los residentes a los que este visitante está autorizado a visitar.
    """
    permission_classes = [IsAdminOrCuidador]

    def get(self, request, visitante_id):
        visitante = get_object_or_404(Visitante, pk=visitante_id)
        autorizaciones = VisitanteResidente.objects.filter(
            visitante=visitante
        ).select_related("residente", "autorizado_por")
        serializer = VisitanteResidenteSerializer(autorizaciones, many=True)
        return Response(serializer.data)


class AutorizarVisitanteView(AuditLogMixin, APIView):
    """
    POST  /api/visitantes/{id}/autorizar/{residente_id}/
    T-83: Crear autorización de visitante para un residente.
    """

    # A1 - Declarar auditoria
    audit_entidad = "autorizaciones_visitantes"

    permission_classes = [IsAdministrador]

    def post(self, request, visitante_id, residente_id):
        visitante = get_object_or_404(Visitante, pk=visitante_id)
        residente = get_object_or_404(Residente, pk=residente_id)

        # Verificar si ya existe la autorización
        existente = VisitanteResidente.objects.filter(
            visitante=visitante, residente=residente
        ).first()

        if existente:
            if existente.estado == "activo":
                return Response(
                    {"error": "Este visitante ya está autorizado para este residente."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            # Reactivar si estaba suspendido
            # A2 - snapshot
            antes = serializar_instancia(existente)
            
            existente.estado = "activo"
            existente.autorizado_por = request.user
            existente.save(update_fields=["estado", "autorizado_por"])

            # A3 - registrar
            self.audit_editar(request, antes, existente)

            return Response(VisitanteResidenteSerializer(existente).data)

        # Crear nueva autorización
        relacion = request.data.get("relacion", "otro")
        vr = VisitanteResidente.objects.create(
            visitante=visitante,
            residente=residente,
            relacion=relacion,
            autorizado_por=request.user,
        )

        # A3 - Registrar auditoría de creación
        self.audit_crear(request, vr)

        return Response(
            VisitanteResidenteSerializer(vr).data, status=status.HTTP_201_CREATED
        )


class SuspenderAutorizacionView(APIView):
    """
    PATCH /api/visitantes/{id}/autorizar/{residente_id}/suspender/
    T-83: Suspender autorización — bloquea futuros registros de visita.
    """

    permission_classes = [IsAdministrador]

    def patch(self, request, visitante_id, residente_id):
        vr = get_object_or_404(
            VisitanteResidente, visitante_id=visitante_id, residente_id=residente_id
        )
        if vr.estado == "suspendido":
            return Response(
                {"error": "Esta autorización ya está suspendida."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        vr.estado = "suspendido"
        vr.save(update_fields=["estado"])
        return Response(
            {
                "mensaje": "Autorización suspendida. El visitante no podrá registrar nuevas visitas.",
                "estado": vr.estado,
            }
        )


# ── T-84, T-85 — Registros de Visita ──────────────────────


class RegistroVisitaListCreateView(APIView):
    """
    GET  /api/visitas/  → listar visitas
    POST /api/visitas/  → registrar ingreso (T-85)
    """

    permission_classes = [IsAdminOrCuidador]

    def get(self, request):
        queryset = RegistroVisita.objects.all().select_related(
            "visitante_residente__visitante",
            "visitante_residente__residente",
            "registrado_por",
        )
        # Filtro por residente
        residente_id = request.query_params.get("residente_id")
        if residente_id:
            queryset = queryset.filter(visitante_residente__residente_id=residente_id)
        estado = request.query_params.get("estado")
        if estado:
            queryset = queryset.filter(estado=estado)
        serializer = RegistroVisitaSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        """
        T-85: Registrar ingreso.
        Acepta visitante_residente (ID directo) O visitante_id + residente_id.
        """
        vr_id        = request.data.get("visitante_residente")
        visitante_id = request.data.get("visitante_id")
        residente_id = request.data.get("residente_id")

        # Resolver la autorización
        if vr_id:
            vr = get_object_or_404(VisitanteResidente, pk=vr_id)
        elif visitante_id and residente_id:
            vr = VisitanteResidente.objects.filter(
                visitante_id=visitante_id,
                residente_id=residente_id,
            ).first()
            if not vr:
                return Response(
                    {"error": "Este visitante no está autorizado para ese residente."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            return Response(
                {"error": "Debe enviar visitante_residente o visitante_id + residente_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Visitante suspendido no puede ingresar
        if vr.estado == "suspendido":
            return Response(
                {"error": "Esta autorización está suspendida. El visitante no puede ingresar."},
                status=status.HTTP_403_FORBIDDEN,
            )

        registro = RegistroVisita.objects.create(
            visitante_residente=vr,
            registrado_por=request.user,
            estado="en_curso",
            observaciones=request.data.get("observaciones", ""),
        )
        return Response(
            RegistroVisitaSerializer(registro).data, status=status.HTTP_201_CREATED
        )

class RegistroVisitaSalidaView(APIView):
    """
    PATCH /api/visitas/{id}/salida/
    T-85: Registrar salida — actualiza fecha_hora_salida y estado=finalizada.
    """

    permission_classes = [IsAdminOrCuidador]

    def patch(self, request, pk):
        registro = get_object_or_404(RegistroVisita, pk=pk)

        if registro.estado == "finalizada":
            return Response(
                {"error": "Esta visita ya fue finalizada."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        registro.fecha_hora_salida = timezone.now()
        registro.estado = "finalizada"
        registro.save(update_fields=["fecha_hora_salida", "estado"])

        return Response(RegistroVisitaSerializer(registro).data)


# ── Historial de visitas del residente (RF-35) ─────────────


class HistorialVisitasResidenteView(APIView):
    """
    GET /api/residentes/{id}/visitas/
    T-85, RF-35: Historial completo con filtros por fecha y visitante.
    """

    permission_classes = [IsAdminOrCuidador]

    def get(self, request, pk):
        residente = get_object_or_404(Residente, pk=pk)
        queryset = RegistroVisita.objects.filter(
            visitante_residente__residente=residente
        ).select_related(
            "visitante_residente__visitante",
            "visitante_residente__residente",
            "registrado_por",
        )

        # Filtros opcionales
        fecha_desde = request.query_params.get("fecha_desde")
        fecha_hasta = request.query_params.get("fecha_hasta")
        visitante_id = request.query_params.get("visitante_id")

        if fecha_desde:
            queryset = queryset.filter(fecha_hora_entrada__date__gte=fecha_desde)
        if fecha_hasta:
            queryset = queryset.filter(fecha_hora_entrada__date__lte=fecha_hasta)
        if visitante_id:
            queryset = queryset.filter(visitante_residente__visitante_id=visitante_id)

        serializer = RegistroVisitaSerializer(queryset, many=True)
        return Response(serializer.data)
    
class ResidenteAutorizacionesView(APIView):
    """
    GET /api/residentes/{residente_id}/autorizaciones/
    Lista los visitantes autorizados para este residente.
    """
    permission_classes = [IsAdminOrCuidador]

    def get(self, request, residente_id):
        residente = get_object_or_404(Residente, pk=residente_id)
        autorizaciones = VisitanteResidente.objects.filter(
            residente=residente
        ).select_related("visitante", "autorizado_por")
        serializer = VisitanteResidenteSerializer(autorizaciones, many=True)
        return Response(serializer.data)