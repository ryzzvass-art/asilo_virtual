from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Count
from datetime import timedelta
from auditoria.mixins import AuditLogMixin, serializar_instancia

from .models import Visitante, VisitanteResidente, RegistroVisita
from .serializers import (
    VisitanteSerializer,
    VisitanteResidenteSerializer,
    RegistroVisitaSerializer,
)
from usuarios.permissions import IsAdministrador, IsAdminOrCuidador
from residentes.models import Residente

# ── T-82, T-83 — Visitantes y Autorizaciones ──────────────


class VisitanteListCreateView(AuditLogMixin, APIView):
    """
    GET  /api/visitantes/  → listar visitantes
                             Filtros: ?busqueda= (nombre O C.I.),
                             ?nombre= y ?dni= (compatibilidad)
    POST /api/visitantes/  → registrar visitante (solo Admin)
    """

    audit_entidad = "visitantes"

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdministrador()]
        return [IsAdminOrCuidador()]

    def get(self, request):
        queryset = Visitante.objects.all().select_related("registrado_por")

        # Búsqueda unificada: nombre O C.I. en una sola query
        busqueda = request.query_params.get("busqueda")
        if busqueda:
            queryset = queryset.filter(
                Q(nombre__icontains=busqueda) | Q(dni__icontains=busqueda)
            )

        # Filtros individuales (compatibilidad con código existente)
        nombre = request.query_params.get("nombre")
        dni = request.query_params.get("dni")
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
        visitante = serializer.save(registrado_por=request.user)

        # Auditoría de creación
        self.audit_crear(request, visitante)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class VisitanteDetailView(AuditLogMixin, APIView):
    """
    GET   /api/visitantes/{id}/  → detalle (admin y cuidador)
    PATCH /api/visitantes/{id}/  → editar (solo admin) — nombre, dni, telefono
    """

    audit_entidad = "visitantes"

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [IsAdministrador()]
        return [IsAdminOrCuidador()]

    def get(self, request, pk):
        visitante = get_object_or_404(Visitante, pk=pk)
        return Response(VisitanteSerializer(visitante).data)

    def patch(self, request, pk):
        visitante = get_object_or_404(Visitante, pk=pk)

        # Snapshot antes del cambio (para auditoría)
        antes = serializar_instancia(visitante)

        serializer = VisitanteSerializer(visitante, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        visitante = serializer.save()

        # Auditoría de edición
        self.audit_editar(request, antes, visitante)

        return Response(serializer.data)


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


class SuspenderAutorizacionView(AuditLogMixin, APIView):
    """
    PATCH /api/visitantes/{id}/autorizar/{residente_id}/suspender/
    T-83: Suspender autorización — bloquea futuros registros de visita.
    """

    audit_entidad = "autorizaciones_visitantes"

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

        # Snapshot antes del cambio
        antes = serializar_instancia(vr)

        vr.estado = "suspendido"
        vr.save(update_fields=["estado"])

        # Auditoría de edición (suspender)
        self.audit_editar(request, antes, vr)

        return Response(
            {
                "mensaje": "Autorización suspendida. El visitante no podrá registrar nuevas visitas.",
                "estado": vr.estado,
            }
        )


# ── T-84, T-85 — Registros de Visita ──────────────────────


class RegistroVisitaListCreateView(AuditLogMixin, APIView):
    """
    GET  /api/visitas/  → listar visitas (admin y cuidador)
                          Filtros: ?residente_id=, ?estado=,
                          ?fecha_desde=, ?fecha_hasta=
    POST /api/visitas/  → registrar ingreso (solo admin)
    """

    audit_entidad = "registros_visita"

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdministrador()]
        return [IsAdminOrCuidador()]

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

        # Filtros de fecha opcionales (mismos nombres que el historial por residente)
        fecha_desde = request.query_params.get("fecha_desde")
        fecha_hasta = request.query_params.get("fecha_hasta")
        if fecha_desde:
            queryset = queryset.filter(fecha_hora_entrada__date__gte=fecha_desde)
        if fecha_hasta:
            queryset = queryset.filter(fecha_hora_entrada__date__lte=fecha_hasta)

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

        # Auditoría de creación (registro de ingreso)
        self.audit_crear(request, registro)

        return Response(
            RegistroVisitaSerializer(registro).data, status=status.HTTP_201_CREATED
        )


class RegistroVisitaSalidaView(AuditLogMixin, APIView):
    """
    PATCH /api/visitas/{id}/salida/
    Registrar salida — actualiza fecha_hora_salida y estado=finalizada.
    Solo administrador.
    """

    audit_entidad = "registros_visita"

    permission_classes = [IsAdministrador]

    def patch(self, request, pk):
        registro = get_object_or_404(RegistroVisita, pk=pk)

        if registro.estado == "finalizada":
            return Response(
                {"error": "Esta visita ya fue finalizada."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Snapshot antes del cambio
        antes = serializar_instancia(registro)

        registro.fecha_hora_salida = timezone.now()
        registro.estado = "finalizada"
        registro.save(update_fields=["fecha_hora_salida", "estado"])

        # Auditoría de edición (registro de salida)
        self.audit_editar(request, antes, registro)

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


# ── Resumen para el Dashboard ──────────────────────────────


class ResumenDashboardVisitasView(APIView):
    """
    GET /api/visitas/resumen-dashboard/
    Métricas agregadas + listas para los modales del Dashboard.
    """
    permission_classes = [IsAdminOrCuidador]

    def get(self, request):
        hoy = timezone.localdate()
        inicio_semana = hoy - timedelta(days=6)  # últimos 7 días incluyendo hoy

        # ── Contadores ──
        visitantes_total = Visitante.objects.count()
        visitantes_con_autorizacion_qs = (
            Visitante.objects
            .filter(autorizaciones__estado="activo")
            .distinct()
        )
        visitantes_con_autorizacion = visitantes_con_autorizacion_qs.count()

        autorizaciones_activas     = VisitanteResidente.objects.filter(estado="activo").count()
        autorizaciones_suspendidas = VisitanteResidente.objects.filter(estado="suspendido").count()

        visitas_hoy_qs = (
            RegistroVisita.objects
            .filter(fecha_hora_entrada__date=hoy)
            .select_related(
                "visitante_residente__visitante",
                "visitante_residente__residente",
            )
            .order_by("-fecha_hora_entrada")
        )
        visitas_hoy = visitas_hoy_qs.count()

        en_curso_qs = (
            RegistroVisita.objects
            .filter(estado="en_curso")
            .select_related(
                "visitante_residente__visitante",
                "visitante_residente__residente",
            )
            .order_by("-fecha_hora_entrada")
        )
        visitas_en_curso_count = en_curso_qs.count()

        # ── Helpers ──
        def fmt_residente(r):
            return f"{r.nombre} {r.apellido}"

        def fmt_hora(dt):
            return timezone.localtime(dt).strftime("%H:%M")

        # ── Listas para los modales ──
        visitas_en_curso = [
            {
                "id": v.id,
                "visitante":          v.visitante_residente.visitante.nombre,
                "visitante_dni":      v.visitante_residente.visitante.dni,
                "residente":          fmt_residente(v.visitante_residente.residente),
                "fecha_hora_entrada": v.fecha_hora_entrada.isoformat(),
            }
            for v in en_curso_qs[:8]
        ]

        visitas_hoy_lista = [
            {
                "visitante": v.visitante_residente.visitante.nombre,
                "residente": fmt_residente(v.visitante_residente.residente),
                "hora":      fmt_hora(v.fecha_hora_entrada),
            }
            for v in visitas_hoy_qs[:50]
        ]

        visitantes_lista = [
            {"nombre": v.nombre, "dni": v.dni, "telefono": v.telefono or "—"}
            for v in Visitante.objects.order_by("nombre")[:200]
        ]

        visitantes_con_autorizacion_lista = [
            {"nombre": v.nombre, "dni": v.dni}
            for v in visitantes_con_autorizacion_qs.order_by("nombre")[:200]
        ]

        suspendidas_qs = (
            VisitanteResidente.objects
            .filter(estado="suspendido")
            .select_related("visitante", "residente")
            .order_by("-fecha_autorizacion")
        )
        autorizaciones_suspendidas_lista = [
            {
                "visitante": a.visitante.nombre,
                "residente": fmt_residente(a.residente),
                "relacion":  a.relacion,
            }
            for a in suspendidas_qs[:100]
        ]

        # ── Gráfico últimos 7 días ──
        agrupado = (
            RegistroVisita.objects
            .filter(fecha_hora_entrada__date__gte=inicio_semana)
            .values("fecha_hora_entrada__date")
            .annotate(total=Count("id"))
        )
        mapa = {row["fecha_hora_entrada__date"]: row["total"] for row in agrupado}
        visitas_ultimos_7_dias = []
        for i in range(7):
            fecha = inicio_semana + timedelta(days=i)
            visitas_ultimos_7_dias.append({
                "fecha": fecha.isoformat(),
                "total": mapa.get(fecha, 0),
            })

        return Response({
            # Métricas
            "visitantes_total":               visitantes_total,
            "visitantes_con_autorizacion":    visitantes_con_autorizacion,
            "autorizaciones_activas":         autorizaciones_activas,
            "autorizaciones_suspendidas":     autorizaciones_suspendidas,
            "visitas_hoy":                    visitas_hoy,
            "visitas_en_curso_count":         visitas_en_curso_count,
            # Listas
            "visitas_en_curso":               visitas_en_curso,
            "visitas_hoy_lista":              visitas_hoy_lista,
            "visitantes_lista":               visitantes_lista,
            "visitantes_con_autorizacion_lista": visitantes_con_autorizacion_lista,
            "autorizaciones_suspendidas_lista":  autorizaciones_suspendidas_lista,
            # Gráfico
            "visitas_ultimos_7_dias":         visitas_ultimos_7_dias,
        })
