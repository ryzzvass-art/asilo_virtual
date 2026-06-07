from django.urls import path
from .views import (
    MedicamentoListCreateView,
    MedicamentoDetailView,
    MedicamentoArchivarView,
    StockListCreateView,
    StockDetailView,
    AlertasStockView,
    PrescripcionListCreateView,
    PrescripcionDetailView,
    PrescripcionFinalizarView,
    AdministracionCreateView,
    AdministracionDetailView,
    AdministracionHistorialView,
    MovimientoStockHistorialView,
    MedicamentosResumenDashboardView
)

urlpatterns = [
    
    path(
        "medicamentos/resumen-dashboard/",
        MedicamentosResumenDashboardView.as_view(),
        name="medicamentos-resumen-dashboard",
    ),
    path(
        "medicamentos/",
        MedicamentoListCreateView.as_view(),
        name="medicamento-list-create",
    ),
    
    path(
        "medicamentos/<int:pk>/",
        MedicamentoDetailView.as_view(),
        name="medicamento-detail",
    ),
    # PATCH /api/medicamentos/{id}/archivar/  → archivar (solo Admin)
    path(
        "medicamentos/<int:pk>/archivar/",
        MedicamentoArchivarView.as_view(),
        name="medicamento-archivar",
    ),
    # ── Stock por lote ──────────────────────────────────────
    # GET  /api/medicamentos/{id}/stock/           → listar lotes
    # POST /api/medicamentos/{id}/stock/           → agregar lote (solo Admin)
    path(
        "medicamentos/<int:pk>/stock/",
        StockListCreateView.as_view(),
        name="stock-list-create",
    ),
    # PATCH /api/medicamentos/{id}/stock/{lote_id}/  → actualizar lote (solo Admin)
    path(
        "medicamentos/<int:pk>/stock/<int:lote_id>/",
        StockDetailView.as_view(),
        name="stock-detail",
    ),
       path(
        "medicamentos/<int:pk>/movimientos/",
        MovimientoStockHistorialView.as_view(),
        name="movimiento-historial",
    ),
    # ── Alertas ─────────────────────────────────────────────
    # GET /api/alertas/stock/  → lotes con alertas activas
    path("alertas/stock/", AlertasStockView.as_view(), name="alertas-stock"),
    # ── Prescripciones ──────────────────────────────────────
    path(
        "residentes/<int:pk>/medicamentos/",
        PrescripcionListCreateView.as_view(),
        name="prescripcion-list-create",
    ),
    path(
        "residentes/<int:pk>/medicamentos/<int:pm_id>/",
        PrescripcionDetailView.as_view(),
        name="prescripcion-detail",
    ),
    path(
        "residentes/<int:pk>/medicamentos/<int:pm_id>/finalizar/",
        PrescripcionFinalizarView.as_view(),
        name="prescripcion-finalizar",
    ),
    # ── Administraciones ────────────────────────────────────
    path(
        "administraciones/",
        AdministracionCreateView.as_view(),
        name="administracion-create",
    ),
    path(
        "administraciones/<int:adm_id>/",
        AdministracionDetailView.as_view(),
        name="administracion-detail",
    ),
    path(
        "residentes/<int:pk>/administraciones/",
        AdministracionHistorialView.as_view(),
        name="administracion-historial",
    ),
]
