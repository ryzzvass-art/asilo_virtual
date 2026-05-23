from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from auditoria.mixins import AuditLogMixin,serializar_instancia

# Necesario para el F() en get_alertas_stock
from django.db import models

from .models import (
    CatalogoMedicamento,
    StockMedicamento,
    ResidenteMedicamento,
    AdministracionMedicamento,
)
from .serializers import (
    CatalogoMedicamentoSerializer,
    CatalogoMedicamentoEditarSerializer,
    StockMedicamentoSerializer,
    ResidenteMedicamentoSerializer,
    PrescripcionFinalizarSerializer,
    AdministracionMedicamentoSerializer,
)
from usuarios.permissions import IsAdministrador, IsAdminOrCuidador
from residentes.models import Residente
from datetime import datetime, timedelta

# ── T-40, T-41 — CRUD Catálogo ─────────────────────────────


class MedicamentoListCreateView(APIView):
    """
    GET  /api/medicamentos/  → listar activos (todos los roles)
    POST /api/medicamentos/  → crear (solo Admin)
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdministrador()]
        return [IsAdminOrCuidador()]

    def get(self, request):
        # Por defecto solo activos — con ?incluir_archivados=true muestra todos (T-41)
        incluir_archivados = request.query_params.get("incluir_archivados", "false")
        if incluir_archivados.lower() == "true":
            queryset = CatalogoMedicamento.objects.all()
        else:
            queryset = CatalogoMedicamento.objects.filter(estado="activo")

        # Filtro opcional por nombre
        nombre = request.query_params.get("nombre")
        if nombre:
            queryset = queryset.filter(nombre_comercial__icontains=nombre)

        serializer = CatalogoMedicamentoSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = CatalogoMedicamentoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save(creado_por=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MedicamentoDetailView(APIView):
    """
    GET        /api/medicamentos/{id}/          → detalle
    PUT/PATCH  /api/medicamentos/{id}/          → editar (solo Admin)
    """

    def get_permissions(self):
        if self.request.method in ["PUT", "PATCH"]:
            return [IsAdministrador()]
        return [IsAdminOrCuidador()]

    def get(self, request, pk):
        medicamento = get_object_or_404(CatalogoMedicamento, pk=pk)
        serializer = CatalogoMedicamentoSerializer(medicamento)
        return Response(serializer.data)

    def patch(self, request, pk):
        medicamento = get_object_or_404(CatalogoMedicamento, pk=pk)
        serializer = CatalogoMedicamentoEditarSerializer(
            medicamento, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(CatalogoMedicamentoSerializer(medicamento).data)


class MedicamentoArchivarView(AuditLogMixin, APIView):
    """
    PATCH /api/medicamentos/{id}/archivar/  → archivar (T-41)
    Solo Admin. Archivado no aparece en listados por defecto.
    """

    # A1 - Declarar auditoria
    audit_entidad = "medicamentos"

    permission_classes = [IsAdministrador]

    def patch(self, request, pk):
        medicamento = get_object_or_404(CatalogoMedicamento, pk=pk)

        if medicamento.estado == "archivado":
            return Response(
                {"error": "Este medicamento ya está archivado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # A2 - snapshot
        antes = serializar_instancia(medicamento)

        medicamento.estado = "archivado"
        medicamento.save(update_fields=["estado"])

        # A3 - registrar
        self.audit_editar(request, antes, medicamento)

        return Response(
            {
                "mensaje": f"'{medicamento.nombre_comercial}' archivado correctamente.",
                "id": medicamento.pk,
                "estado": medicamento.estado,
            }
        )


# ── T-43, T-44 — Stock por lote ────────────────────────────


class StockListCreateView(APIView):
    """
    GET  /api/medicamentos/{id}/stock/  → listar lotes
    POST /api/medicamentos/{id}/stock/  → agregar lote
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdministrador()]
        return [IsAdminOrCuidador()]

    def get(self, request, pk):
        medicamento = get_object_or_404(CatalogoMedicamento, pk=pk)
        lotes = StockMedicamento.objects.filter(medicamento=medicamento).select_related(
            "actualizado_por"
        )
        serializer = StockMedicamentoSerializer(lotes, many=True)
        return Response(serializer.data)

    def post(self, request, pk):
        medicamento = get_object_or_404(CatalogoMedicamento, pk=pk)
        serializer = StockMedicamentoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save(medicamento=medicamento, actualizado_por=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class StockDetailView(APIView):
    """
    PATCH /api/medicamentos/{id}/stock/{lote_id}/  → actualizar cantidad/umbral (T-43)
    """

    permission_classes = [IsAdministrador]

    def patch(self, request, pk, lote_id):
        medicamento = get_object_or_404(CatalogoMedicamento, pk=pk)
        lote = get_object_or_404(StockMedicamento, pk=lote_id, medicamento=medicamento)
        serializer = StockMedicamentoSerializer(lote, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save(actualizado_por=request.user)
        return Response(serializer.data)


# ── T-45, T-46 — Alertas de stock ─────────────────────────


def get_alertas_stock():
    """
    T-46: Función de servicio reutilizable.
    Retorna lotes con stock_bajo O vencimiento_proximo.
    Se usará en el dashboard del Sprint 9.
    """
    hoy = timezone.now().date()
    limite = hoy + timedelta(days=30)
    alertas = []

    lotes = StockMedicamento.objects.select_related(
        "medicamento", "actualizado_por"
    ).filter(
        # stock bajo O vencimiento próximo
        cantidad__lte=models.F("umbral_minimo")
    ) | StockMedicamento.objects.select_related(
        "medicamento", "actualizado_por"
    ).filter(
        fecha_vencimiento__lte=limite
    )

    # Eliminar duplicados (un lote puede tener ambas alertas)
    lotes_vistos = set()
    for lote in lotes:
        if lote.pk in lotes_vistos:
            continue
        lotes_vistos.add(lote.pk)

        tipos = []
        if lote.cantidad <= lote.umbral_minimo:
            tipos.append("stock_bajo")
        if lote.fecha_vencimiento <= limite:
            tipos.append("vencimiento_proximo")

        alertas.append(
            {
                "lote_id": lote.pk,
                "lote": lote.lote,
                "medicamento_id": lote.medicamento.pk,
                "medicamento": lote.medicamento.nombre_comercial,
                "cantidad": lote.cantidad,
                "umbral_minimo": lote.umbral_minimo,
                "fecha_vencimiento": lote.fecha_vencimiento,
                "tipos_alerta": tipos,
            }
        )

    return alertas


class AlertasStockView(APIView):
    """
    GET /api/alertas/stock/  → lotes con stock bajo o vencimiento próximo (T-45)
    """

    permission_classes = [IsAdminOrCuidador]

    def get(self, request):
        alertas = get_alertas_stock()
        return Response(
            {
                "total": len(alertas),
                "alertas": alertas,
            }
        )


class PrescripcionListCreateView(AuditLogMixin, APIView):
    """
    GET  /api/residentes/{id}/medicamentos/  → listar prescripciones activas (T-50)
    POST /api/residentes/{id}/medicamentos/  → crear prescripción (T-49)
    """

    # A1 - Declarar auditoria
    audit_entidad = "prescripciones"

    permission_classes = [IsAdminOrCuidador]

    def get(self, request, pk):
        residente = get_object_or_404(Residente, pk=pk)
        # Por defecto solo activas — con ?incluir_finalizadas=true muestra todas
        incluir = request.query_params.get("incluir_finalizadas", "false")
        if incluir.lower() == "true":
            queryset = ResidenteMedicamento.objects.filter(residente=residente)
        else:
            queryset = ResidenteMedicamento.objects.filter(
                residente=residente, estado="activo"
            )
        queryset = queryset.select_related("medicamento", "prescrito_por")
        serializer = ResidenteMedicamentoSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request, pk):
        """
        T-49: Crear prescripción.
        Valida que medicamento esté activo.
        Verifica contraindicaciones contra condiciones_cronicas del residente (RF-10-B).
        """
        residente = get_object_or_404(Residente, pk=pk)
        serializer = ResidenteMedicamentoSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        medicamento = serializer.validated_data["medicamento"]

        # RF-10-B: verificar contraindicaciones vs condiciones crónicas del residente
        advertencias = []
        try:
            historial = residente.historial_medico
            if historial.condiciones_cronicas and medicamento.contraindicaciones:
                # Búsqueda simple de palabras clave en común
                condiciones = historial.condiciones_cronicas.lower()
                contraindicaciones = medicamento.contraindicaciones.lower()
                palabras = [
                    p.strip() for p in condiciones.split(",") if len(p.strip()) > 3
                ]
                for palabra in palabras:
                    if palabra in contraindicaciones:
                        advertencias.append(
                            f"Posible contraindicación: '{palabra}' aparece en las contraindicaciones del medicamento."
                        )
        except Exception:
            pass

        prescripcion = serializer.save(residente=residente, prescrito_por=request.user)

        # A3 - Registrar auditoría de creación
        self.audit_crear(request, prescripcion)

        response_data = serializer.data
        if advertencias:
            response_data = dict(serializer.data)
            response_data["advertencias"] = advertencias

        return Response(response_data, status=status.HTTP_201_CREATED)

# ── T-48, T-49, T-50 — Prescripciones ─────────────────────


class PrescripcionDetailView(APIView):
    """
    PATCH /api/residentes/{id}/medicamentos/{pm_id}/          → editar (T-50)
    PATCH /api/residentes/{id}/medicamentos/{pm_id}/finalizar/ → finalizar (T-50)
    """

    permission_classes = [IsAdminOrCuidador]

    def patch(self, request, pk, pm_id):
        residente = get_object_or_404(Residente, pk=pk)
        prescripcion = get_object_or_404(
            ResidenteMedicamento, pk=pm_id, residente=residente
        )
        serializer = ResidenteMedicamentoSerializer(
            prescripcion, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)


class PrescripcionFinalizarView(APIView):
    """PATCH /api/residentes/{id}/medicamentos/{pm_id}/finalizar/"""

    permission_classes = [IsAdminOrCuidador]

    def patch(self, request, pk, pm_id):
        residente = get_object_or_404(Residente, pk=pk)
        prescripcion = get_object_or_404(
            ResidenteMedicamento, pk=pm_id, residente=residente
        )
        if prescripcion.estado == "finalizado":
            return Response(
                {"error": "Esta prescripción ya está finalizada."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        prescripcion.estado = "finalizado"
        if not prescripcion.fecha_fin:
            prescripcion.fecha_fin = timezone.now().date()
        prescripcion.save()
        return Response(
            {
                "mensaje": "Prescripción finalizada correctamente.",
                "id": prescripcion.pk,
                "estado": prescripcion.estado,
                "fecha_fin": prescripcion.fecha_fin,
            }
        )


# ── T-51, T-52, T-53 — Administraciones ───────────────────


class AdministracionCreateView(APIView):
    """
    POST /api/administraciones/  → registrar toma (T-52)
    """

    permission_classes = [IsAdminOrCuidador]

    def post(self, request):
        serializer = AdministracionMedicamentoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save(realizado_por=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdministracionDetailView(APIView):
    """
    PATCH /api/administraciones/{id}/  → corregir registro (T-53)
    Solo Admin puede corregir, y solo dentro de las primeras 2 horas.
    """

    permission_classes = [IsAdministrador]

    def patch(self, request, adm_id):
        administracion = get_object_or_404(AdministracionMedicamento, pk=adm_id)

        # T-53: corrección solo dentro de las primeras 2 horas
        limite = administracion.fecha_hora_programada + timedelta(hours=2)
        if timezone.now() > limite:
            return Response(
                {
                    "error": "Solo se puede corregir un registro dentro de las 2 horas siguientes a la toma programada."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = AdministracionMedicamentoSerializer(
            administracion, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)


# ── T-54, T-55 — Historial de administraciones ────────────


class AdministracionHistorialView(APIView):
    """
    GET /api/residentes/{id}/administraciones/  → historial con filtros (T-54, T-55)
    """

    permission_classes = [IsAdminOrCuidador]

    def get(self, request, pk):
        residente = get_object_or_404(Residente, pk=pk)

        queryset = AdministracionMedicamento.objects.filter(
            residente_medicamento__residente=residente
        ).select_related(
            "residente_medicamento__medicamento",
            "residente_medicamento__residente",
            "realizado_por",
        )

        # Filtros opcionales
        fecha_desde = request.query_params.get("fecha_desde")
        fecha_hasta = request.query_params.get("fecha_hasta")
        administrado = request.query_params.get("administrado")

        if fecha_desde:
            queryset = queryset.filter(fecha_hora_programada__date__gte=fecha_desde)
        if fecha_hasta:
            queryset = queryset.filter(fecha_hora_programada__date__lte=fecha_hasta)
        if administrado is not None:
            valor = administrado.lower() == "true"
            queryset = queryset.filter(administrado=valor)

        # Paginación
        page = int(request.query_params.get("page", 1))
        page_size = 20
        start = (page - 1) * page_size
        end = start + page_size
        total = queryset.count()
        pagina = queryset[start:end]

        # T-55: resumen por período
        total_programadas = queryset.count()
        total_administradas = queryset.filter(administrado=True).count()
        total_omitidas = queryset.filter(administrado=False).count()

        serializer = AdministracionMedicamentoSerializer(pagina, many=True)
        return Response(
            {
                "total": total,
                "page": page,
                "pages": (total + page_size - 1) // page_size,
                "resumen": {
                    "total_programadas": total_programadas,
                    "total_administradas": total_administradas,
                    "total_omitidas": total_omitidas,
                },
                "results": serializer.data,
            }
        )
