from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from auditoria.mixins import AuditLogMixin, serializar_instancia, registrar_auditoria
from datetime import timedelta
from django.db.models import Count


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
        residente_id = request.query_params.get("residente")

        if estado:
            queryset = queryset.filter(estado=estado)
        if tipo:
            queryset = queryset.filter(tipo=tipo)
        if fecha:
            queryset = queryset.filter(fecha_hora__date=fecha)
        if residente_id:  
            queryset = queryset.filter(participantes__residente_id=residente_id).distinct()

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

class ActividadDetailView(AuditLogMixin, APIView):
    """
    GET        /api/actividades/{id}/  → detalle con participantes
    PUT/PATCH  /api/actividades/{id}/  → editar (solo Admin)
    """

    # A1 - Declarar auditoria
    audit_entidad = "actividades"

    def get_permissions(self):
        if self.request.method in ["PUT", "PATCH"]:
            return [IsAdministrador()]
        return [IsAdminOrCuidador()]

    def get(self, request, pk):
        actividad = get_object_or_404(Actividad, pk=pk)
        data = ActividadSerializer(actividad).data
        participantes = ActividadResidente.objects.filter(
            actividad=actividad
        ).select_related("residente", "asignado_por")
        data["participantes"] = ActividadResidenteSerializer(
            participantes, many=True
        ).data
        return Response(data)

    def patch(self, request, pk):
        actividad = get_object_or_404(Actividad, pk=pk)

        # A2 - snapshot antes de editar
        antes = serializar_instancia(actividad)

        serializer = ActividadSerializer(actividad, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()

        # A3 - registrar auditoría de edición
        actividad.refresh_from_db()
        self.audit_editar(request, antes, actividad)

        return Response(serializer.data)


class ActividadResidenteView(AuditLogMixin, APIView):
    """
    GET    /api/actividades/{id}/residentes/              → listar participantes
    POST   /api/actividades/{id}/residentes/              → asignar residente
    DELETE /api/actividades/{id}/residentes/{residente_id}/ → desasignar
    """

    audit_entidad = "actividad_residentes"
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
                {"error": f"{residente.nombre} {residente.apellido} ya está asignado a esta actividad."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ar = ActividadResidente.objects.create(
            actividad=actividad, residente=residente, asignado_por=request.user
        )

        # AUDITORÍA: registrar asignación de residente a la actividad
        self.audit_crear(request, ar)

        return Response(
            ActividadResidenteSerializer(ar).data, status=status.HTTP_201_CREATED
        )

    def delete(self, request, pk, residente_id):
        actividad = get_object_or_404(Actividad, pk=pk)
        residente = get_object_or_404(Residente, pk=residente_id)
        ar = get_object_or_404(
            ActividadResidente, actividad=actividad, residente=residente
        )

        # AUDITORÍA: snapshot ANTES de borrar (es un borrado real)
        antes = serializar_instancia(ar)
        ar_pk = ar.pk

        ar.delete()

        # AUDITORÍA: registrar desasignación (eliminación)
        registrar_auditoria(
            request=request,
            accion="eliminar",
            entidad_nombre=self.audit_entidad,
            entidad_id=ar_pk,
            datos_anteriores=antes,
            datos_nuevos=None,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)

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
class ActividadCancelarView(AuditLogMixin, APIView):
    """
    PATCH /api/actividades/{id}/cancelar/
    Requiere 'observaciones' (motivo de cancelación).
    """

    audit_entidad = "actividades"
    permission_classes = [IsAdministrador]

    def patch(self, request, pk):
        actividad = get_object_or_404(Actividad, pk=pk)
        if actividad.estado == "cancelada":
            return Response(
                {"error": "Esta actividad ya está cancelada."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Corrección 3: observaciones obligatorias al cancelar
        observaciones = (request.data.get("observaciones") or "").strip()
        if not observaciones:
            return Response(
                {"error": "Debe indicar el motivo de la cancelación."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        antes = serializar_instancia(actividad)

        actividad.estado = "cancelada"
        actividad.observaciones = observaciones
        actividad.save(update_fields=["estado", "observaciones"])

        self.audit_editar(request, antes, actividad)

        return Response(
            {
                "mensaje": f"Actividad '{actividad.nombre}' cancelada.",
                "estado": actividad.estado,
            }
        )


class ActividadRealizadaView(AuditLogMixin, APIView):
    """
    PATCH /api/actividades/{id}/realizada/
    'observaciones' es opcional.
    """

    audit_entidad = "actividades"
    permission_classes = [IsAdminOrCuidador]

    def patch(self, request, pk):
        actividad = get_object_or_404(Actividad, pk=pk)
        if actividad.estado == "cancelada":
            return Response(
                {"error": "No se puede marcar como realizada una actividad cancelada."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        antes = serializar_instancia(actividad)

        observaciones = (request.data.get("observaciones") or "").strip()
        actividad.estado = "realizada"
        if observaciones:
            actividad.observaciones = observaciones
        actividad.save(update_fields=["estado", "observaciones"])

        self.audit_editar(request, antes, actividad)

        return Response(
            {"mensaje": "Actividad marcada como realizada.", "estado": actividad.estado}
        )

class ActividadesResumenDashboardView(APIView):
    """
    GET /api/actividades/resumen-dashboard/
    Resumen de actividades para el dashboard.
    """
    permission_classes = [IsAdminOrCuidador]

    def get(self, request):
        ahora = timezone.now()
        hoy = ahora.date()
        hace_30 = hoy - timedelta(days=30)
        hace_7 = hoy - timedelta(days=6)

        qs = Actividad.objects.all()

        def _fmt_tipo(a):
            if a.tipo == "otro" and a.tipo_otro:
                return a.tipo_otro
            return dict(Actividad.Tipo.choices).get(a.tipo, a.tipo)

        def _serializar(actividades, incluir_motivo=False):
            out = []
            for a in actividades:
                item = {
                    "id": a.id,
                    "nombre": a.nombre,
                    "tipo": _fmt_tipo(a),
                    "fecha_hora": a.fecha_hora.isoformat(),
                    "responsable": a.responsable,
                    "estado": a.estado,
                }
                if incluir_motivo:
                    item["observaciones"] = a.observaciones or "Sin motivo registrado"
                out.append(item)
            return out

        # Listas completas (no las recortamos: el modal las muestra todas)
        programadas = qs.filter(estado="programada", fecha_hora__gte=ahora).order_by("fecha_hora")
        realizadas = qs.filter(estado="realizada", fecha_hora__date__gte=hace_30).order_by("-fecha_hora")
        canceladas = qs.filter(estado="cancelada", fecha_hora__date__gte=hace_30).order_by("-fecha_hora")
        total_mes_qs = qs.filter(fecha_hora__date__gte=hace_30).order_by("-fecha_hora")

        programadas_lista = _serializar(programadas)
        realizadas_lista = _serializar(realizadas)
        canceladas_lista = _serializar(canceladas, incluir_motivo=True)
        total_mes_lista = _serializar(total_mes_qs)

        # Distribución por tipo (últimos 30 días)
        tipos_choices = dict(Actividad.Tipo.choices)
        por_tipo_qs = (
            qs.filter(fecha_hora__date__gte=hace_30)
            .values("tipo")
            .annotate(total=Count("id"))
            .order_by("-total")
        )
        por_tipo = [
            {"tipo": t["tipo"], "label": tipos_choices.get(t["tipo"], t["tipo"]), "total": t["total"]}
            for t in por_tipo_qs
        ]

        # Últimos 7 días
        ultimos_7 = [
            {"fecha": (hace_7 + timedelta(days=i)).isoformat(),
             "total": qs.filter(fecha_hora__date=hace_7 + timedelta(days=i)).count()}
            for i in range(7)
        ]

        return Response({
            "programadas_count": len(programadas_lista),
            "realizadas_mes":    len(realizadas_lista),
            "canceladas_mes":    len(canceladas_lista),
            "total_mes":         len(total_mes_lista),
            "programadas_lista": programadas_lista,
            "realizadas_lista":  realizadas_lista,
            "canceladas_lista":  canceladas_lista,
            "total_mes_lista":   total_mes_lista,
            "por_tipo":          por_tipo,
            "ultimos_7_dias":    ultimos_7,
        })
