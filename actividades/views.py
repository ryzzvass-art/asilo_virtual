from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from auditoria.mixins import AuditLogMixin,serializar_instancia


from .models import Actividad, ActividadResidente
from .serializers import ActividadSerializer, ActividadResidenteSerializer
from usuarios.permissions import IsAdministrador, IsAdminOrCuidador
from residentes.models import Residente

# ── T-78, T-79 — CRUD Actividades ─────────────────────────


class ActividadListCreateView(AuditLogMixin, APIView):
    """
    GET  /api/actividades/  → listar con filtros (todos los roles)
    POST /api/actividades/  → crear (solo Admin)
    """

    # A1 - Declarar auditoria
    audit_entidad = "actividades"

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdministrador()]
        return [IsAdminOrCuidador()]

    def get(self, request):
        queryset = Actividad.objects.all().select_related("creado_por")

        # Filtros opcionales
        estado = request.query_params.get("estado")
        tipo = request.query_params.get("tipo")
        fecha = request.query_params.get("fecha")

        if estado:
            queryset = queryset.filter(estado=estado)
        if tipo:
            queryset = queryset.filter(tipo=tipo)
        if fecha:
            queryset = queryset.filter(fecha_hora__date=fecha)

        serializer = ActividadSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ActividadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        actividad = serializer.save(creado_por=request.user)

        # A3 - Registrar auditoría de creación
        self.audit_crear(request, actividad)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ActividadDetailView(APIView):
    """
    GET        /api/actividades/{id}/  → detalle con participantes
    PUT/PATCH  /api/actividades/{id}/  → editar (solo Admin)
    """

    def get_permissions(self):
        if self.request.method in ["PUT", "PATCH"]:
            return [IsAdministrador()]
        return [IsAdminOrCuidador()]

    def get(self, request, pk):
        actividad = get_object_or_404(Actividad, pk=pk)
        data = ActividadSerializer(actividad).data
        # Incluir lista de participantes
        participantes = ActividadResidente.objects.filter(
            actividad=actividad
        ).select_related("residente", "asignado_por")
        data["participantes"] = ActividadResidenteSerializer(
            participantes, many=True
        ).data
        return Response(data)

    def patch(self, request, pk):
        actividad = get_object_or_404(Actividad, pk=pk)
        serializer = ActividadSerializer(actividad, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)


class ActividadCancelarView(AuditLogMixin, APIView):
    """
    PATCH /api/actividades/{id}/cancelar/
    T-79: Cancelada queda en sistema para alertas del dashboard.
    """

    # A1 - Declarar auditoria
    audit_entidad = "actividades"

    permission_classes = [IsAdministrador]

    def patch(self, request, pk):
        actividad = get_object_or_404(Actividad, pk=pk)
        if actividad.estado == "cancelada":
            return Response(
                {"error": "Esta actividad ya está cancelada."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # A2 - snapshot
        antes = serializar_instancia(actividad)

        actividad.estado = "cancelada"
        actividad.save(update_fields=["estado"])

        # A3 - registrar
        self.audit_editar(request, antes, actividad)

        return Response(
            {
                "mensaje": f"Actividad '{actividad.nombre}' cancelada.",
                "estado": actividad.estado,
            }
        )


# ── T-80, T-81 — Asignación de Residentes ─────────────────


class ActividadResidenteView(APIView):
    """
    GET    /api/actividades/{id}/residentes/              → listar participantes
    POST   /api/actividades/{id}/residentes/              → asignar residente
    DELETE /api/actividades/{id}/residentes/{residente_id}/ → desasignar
    """

    permission_classes = [IsAdminOrCuidador]

    def get(self, request, pk):
        actividad = get_object_or_404(Actividad, pk=pk)
        participantes = ActividadResidente.objects.filter(
            actividad=actividad
        ).select_related("residente", "asignado_por")
        serializer = ActividadResidenteSerializer(participantes, many=True)
        return Response(serializer.data)

    def post(self, request, pk):
        actividad = get_object_or_404(Actividad, pk=pk)
        residente_id = request.data.get("residente_id")

        if not residente_id:
            return Response(
                {"error": "residente_id es requerido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        residente = get_object_or_404(Residente, pk=residente_id)

        # T-81: Asignación duplicada devuelve 400
        if ActividadResidente.objects.filter(
            actividad=actividad, residente=residente
        ).exists():
            return Response(
                {"error": f"{residente} ya está asignado a esta actividad."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ar = ActividadResidente.objects.create(
            actividad=actividad, residente=residente, asignado_por=request.user
        )
        return Response(
            ActividadResidenteSerializer(ar).data, status=status.HTTP_201_CREATED
        )

    def delete(self, request, pk, residente_id):
        actividad = get_object_or_404(Actividad, pk=pk)
        residente = get_object_or_404(Residente, pk=residente_id)
        ar = get_object_or_404(
            ActividadResidente, actividad=actividad, residente=residente
        )
        ar.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Actividades de hoy (para Sprint 9 dashboard) ───────────


def get_actividades_hoy():
    """
    Función de servicio reutilizable para el dashboard Sprint 9.
    Retorna actividades programadas para el día de hoy.
    """
    hoy = timezone.now().date()
    return (
        Actividad.objects.filter(fecha_hora__date=hoy)
        .prefetch_related("participantes")
        .select_related("creado_por")
    )
