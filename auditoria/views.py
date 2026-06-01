from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import AuditLog
from .serializers import AuditLogSerializer
from usuarios.permissions import IsAdministrador, IsAdminOrCuidador

# ── T-89, T-90 — Consulta del Audit Log ───────────────────


class AuditLogListView(APIView):
    """
    GET /api/audit-log/
    Solo rol administrador — cuidador recibe 403.
    Filtros: ?usuario_id= ?entidad= ?accion= ?fecha_desde= ?fecha_hasta=
    Paginación obligatoria.
    """

    permission_classes = [IsAdministrador]

    def get(self, request):
        queryset = AuditLog.objects.all().select_related("usuario")

        # Filtros opcionales
        usuario_id = request.query_params.get("usuario_id")
        entidad = request.query_params.get("entidad")
        accion = request.query_params.get("accion")
        fecha_desde = request.query_params.get("fecha_desde")
        fecha_hasta = request.query_params.get("fecha_hasta")

        if usuario_id:
            queryset = queryset.filter(usuario_id=usuario_id)
        if entidad:
            queryset = queryset.filter(entidad__icontains=entidad)
        if accion:
            queryset = queryset.filter(accion=accion)
        if fecha_desde:
            queryset = queryset.filter(fecha_hora__date__gte=fecha_desde)
        if fecha_hasta:
            queryset = queryset.filter(fecha_hora__date__lte=fecha_hasta)

        # Paginación
        page = int(request.query_params.get("page", 1))
        page_size = 20
        start = (page - 1) * page_size
        end = start + page_size
        total = queryset.count()

        serializer = AuditLogSerializer(queryset[start:end], many=True)
        return Response(
            {
                "total": total,
                "page": page,
                "pages": (total + page_size - 1) // page_size,
                "results": serializer.data,
            }
        )


class AuditLogDetailView(APIView):
    """
    GET /api/audit-log/{id}/
    T-90: Detalle con datos_anteriores y datos_nuevos formateados.
    """

    permission_classes = [IsAdministrador]

    def get(self, request, pk):
        entrada = get_object_or_404(AuditLog, pk=pk)
        serializer = AuditLogSerializer(entrada)
        return Response(serializer.data)


# T-91, T-92, T-93, T-94


class DashboardView(APIView):
    """
    GET /api/dashboard/
    T-91, T-92, T-93: Consolida en un solo response todas las métricas y alertas.
    Máximo 8 queries SQL usando select_related y prefetch_related.
    """

    permission_classes = [IsAdminOrCuidador]

    def get(self, request):
        from django.utils import timezone
        from residentes.models import Residente
        from medicamentos.views import get_alertas_stock
        from actividades.views import get_actividades_hoy
        from medicamentos.models import AdministracionMedicamento
        from visitas.models import RegistroVisita

        hoy = timezone.now().date()

        # ── Query 1: Resumen de residentes por estado ──────
        from django.db.models import Count

        resumen_residentes = {}
        for item in Residente.objects.values("estado").annotate(total=Count("id")):
            resumen_residentes[item["estado"]] = item["total"]

        # ── Query 2: Tomas omitidas hoy ────────────────────
        tomas_omitidas = (
            AdministracionMedicamento.objects.filter(
                administrado=False, fecha_hora_programada__date=hoy
            )
            .select_related(
                "residente_medicamento__residente", "residente_medicamento__medicamento"
            )
            .values(
                "residente_medicamento__residente__nombre",
                "residente_medicamento__residente__apellido",
                "residente_medicamento__medicamento__nombre_comercial",
                "fecha_hora_programada",
            )[:10]
        )  # Máximo 10 para el dashboard

        tomas_omitidas_list = [
            {
                "residente": f"{t['residente_medicamento__residente__nombre']} {t['residente_medicamento__residente__apellido']}",
                "medicamento": t[
                    "residente_medicamento__medicamento__nombre_comercial"
                ],
                "hora_programada": timezone.localtime(t["fecha_hora_programada"]).strftime("%H:%M"),
            }
            for t in tomas_omitidas
        ]

        # ── Query 3: Actividades hoy ───────────────────────
        actividades_hoy = get_actividades_hoy()
        actividades_count = actividades_hoy.count()

        actividades_canceladas = [
            {
                "id": a.pk,
                "nombre": a.nombre,
                "hora": timezone.localtime(a.fecha_hora).strftime("%H:%M"),
            }
            for a in actividades_hoy.filter(estado="cancelada")
        ]

        # ── Query 4: Visitas en curso ───────────────────────
        visitas_en_curso = (
            RegistroVisita.objects.filter(estado="en_curso")
            .select_related(
                "visitante_residente__visitante",
                "visitante_residente__residente",
            )
            .values(
                "visitante_residente__visitante__nombre",
                "visitante_residente__residente__nombre",
                "visitante_residente__residente__apellido",
                "fecha_hora_entrada",
            )
        )

        visitas_list = [
            {
                "visitante": v["visitante_residente__visitante__nombre"],
                "residente": f"{v['visitante_residente__residente__nombre']} {v['visitante_residente__residente__apellido']}",
                "entrada": timezone.localtime(v["fecha_hora_entrada"]).strftime("%H:%M"),
            }
            for v in visitas_en_curso
        ]

        # ── Query 5: Alertas de stock ──────────────────────
        alertas_stock = get_alertas_stock()

        return Response(
            {
                # T-92: Resumen de residentes
                "resumen_residentes": {
                    "activos": resumen_residentes.get("activo", 0),
                    "hospitalizados": resumen_residentes.get("hospitalizado", 0),
                    "dados_de_alta": resumen_residentes.get("dado_de_alta", 0),
                },
                # T-92: Conteo de actividades hoy
                "actividades_hoy_count": actividades_count,
                # T-91: Los 4 bloques de alertas
                "alertas": {
                    "stock": alertas_stock,
                    "tomas_omitidas_hoy": tomas_omitidas_list,
                    "actividades_canceladas": actividades_canceladas,
                    "visitas_en_curso": visitas_list,
                },
            }
        )


class ActividadesHoyView(APIView):
    """
    GET /api/actividades/hoy/
    T-94: Actividades del día con lista de residentes asignados.
    """

    permission_classes = [IsAdminOrCuidador]

    def get(self, request):
        from actividades.views import get_actividades_hoy
        from actividades.models import ActividadResidente

        actividades = get_actividades_hoy()
        resultado = []

        for a in actividades:
            participantes = ActividadResidente.objects.filter(
                actividad=a
            ).select_related("residente")

            resultado.append(
                {
                    "id": a.pk,
                    "nombre": a.nombre,
                    "tipo": a.tipo,
                    "responsable": a.responsable,
                    "hora": timezone.localtime(a.fecha_hora).strftime("%H:%M"),
                    "estado": a.estado,
                    "participantes": [
                        {
                            "id": p.residente.pk,
                            "nombre": f"{p.residente.nombre} {p.residente.apellido}",
                        }
                        for p in participantes
                    ],
                }
            )

        return Response(
            {
                "fecha": timezone.now().date().isoformat(),
                "total": len(resultado),
                "actividades": resultado,
            }
        )
