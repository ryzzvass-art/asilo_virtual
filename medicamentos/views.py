
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta

from .models import CatalogoMedicamento, StockMedicamento
from .serializers import (
    CatalogoMedicamentoSerializer,
    CatalogoMedicamentoEditarSerializer,
    StockMedicamentoSerializer,
)
from usuarios.permissions import IsAdministrador, IsAdminOrCuidador


# ── T-40, T-41 — CRUD Catálogo ─────────────────────────────

class MedicamentoListCreateView(APIView):
    """
    GET  /api/medicamentos/  → listar activos (todos los roles)
    POST /api/medicamentos/  → crear (solo Admin)
    """

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdministrador()]
        return [IsAdminOrCuidador()]

    def get(self, request):
        # Por defecto solo activos — con ?incluir_archivados=true muestra todos (T-41)
        incluir_archivados = request.query_params.get('incluir_archivados', 'false')
        if incluir_archivados.lower() == 'true':
            queryset = CatalogoMedicamento.objects.all()
        else:
            queryset = CatalogoMedicamento.objects.filter(estado='activo')

        # Filtro opcional por nombre
        nombre = request.query_params.get('nombre')
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
        if self.request.method in ['PUT', 'PATCH']:
            return [IsAdministrador()]
        return [IsAdminOrCuidador()]

    def get(self, request, pk):
        medicamento = get_object_or_404(CatalogoMedicamento, pk=pk)
        serializer  = CatalogoMedicamentoSerializer(medicamento)
        return Response(serializer.data)

    def patch(self, request, pk):
        medicamento = get_object_or_404(CatalogoMedicamento, pk=pk)
        serializer  = CatalogoMedicamentoEditarSerializer(
            medicamento, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(CatalogoMedicamentoSerializer(medicamento).data)


class MedicamentoArchivarView(APIView):
    """
    PATCH /api/medicamentos/{id}/archivar/  → archivar (T-41)
    Solo Admin. Archivado no aparece en listados por defecto.
    """
    permission_classes = [IsAdministrador]

    def patch(self, request, pk):
        medicamento = get_object_or_404(CatalogoMedicamento, pk=pk)

        if medicamento.estado == 'archivado':
            return Response(
                {"error": "Este medicamento ya está archivado."},
                status=status.HTTP_400_BAD_REQUEST
            )

        medicamento.estado = 'archivado'
        medicamento.save(update_fields=['estado'])
        return Response({
            "mensaje": f"'{medicamento.nombre_comercial}' archivado correctamente.",
            "id":     medicamento.pk,
            "estado": medicamento.estado,
        })


# ── T-43, T-44 — Stock por lote ────────────────────────────

class StockListCreateView(APIView):
    """
    GET  /api/medicamentos/{id}/stock/  → listar lotes
    POST /api/medicamentos/{id}/stock/  → agregar lote
    """

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdministrador()]
        return [IsAdminOrCuidador()]

    def get(self, request, pk):
        medicamento = get_object_or_404(CatalogoMedicamento, pk=pk)
        lotes       = StockMedicamento.objects.filter(
            medicamento=medicamento
        ).select_related('actualizado_por')
        serializer  = StockMedicamentoSerializer(lotes, many=True)
        return Response(serializer.data)

    def post(self, request, pk):
        medicamento = get_object_or_404(CatalogoMedicamento, pk=pk)
        serializer  = StockMedicamentoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save(
            medicamento=medicamento,
            actualizado_por=request.user
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class StockDetailView(APIView):
    """
    PATCH /api/medicamentos/{id}/stock/{lote_id}/  → actualizar cantidad/umbral (T-43)
    """
    permission_classes = [IsAdministrador]

    def patch(self, request, pk, lote_id):
        medicamento = get_object_or_404(CatalogoMedicamento, pk=pk)
        lote        = get_object_or_404(StockMedicamento, pk=lote_id, medicamento=medicamento)
        serializer  = StockMedicamentoSerializer(lote, data=request.data, partial=True)
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
    hoy      = timezone.now().date()
    limite   = hoy + timedelta(days=30)
    alertas  = []

    lotes = StockMedicamento.objects.select_related(
        'medicamento', 'actualizado_por'
    ).filter(
        # stock bajo O vencimiento próximo
        cantidad__lte=models.F('umbral_minimo')
    ) | StockMedicamento.objects.select_related(
        'medicamento', 'actualizado_por'
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

        alertas.append({
            "lote_id":           lote.pk,
            "lote":              lote.lote,
            "medicamento_id":    lote.medicamento.pk,
            "medicamento":       lote.medicamento.nombre_comercial,
            "cantidad":          lote.cantidad,
            "umbral_minimo":     lote.umbral_minimo,
            "fecha_vencimiento": lote.fecha_vencimiento,
            "tipos_alerta":      tipos,
        })

    return alertas


class AlertasStockView(APIView):
    """
    GET /api/alertas/stock/  → lotes con stock bajo o vencimiento próximo (T-45)
    """
    permission_classes = [IsAdminOrCuidador]

    def get(self, request):
        alertas = get_alertas_stock()
        return Response({
            "total":   len(alertas),
            "alertas": alertas,
        })


# Necesario para el F() en get_alertas_stock
from django.db import models
