from django.urls import path
from .views import (
    RestriccionListCreateView,
    RestriccionDetailView,
    RestriccionArchivarView,
    AlimentoListCreateView,
    AlimentoDetailView,
    AlimentoActivarView,
    AlimentoRestriccionView,
    ResidenteRestriccionView,
    ResidenteRestriccionRevocarView,
    PlanListCreateView,
    PlanDetailView,
    ComidaListCreateView,
    ComidaDetailView,
)

urlpatterns = [
    # ── Catálogo de Restricciones ───────────────────────────
    path(
        "restricciones/",
        RestriccionListCreateView.as_view(),
        name="restriccion-list-create",
    ),
    path(
        "restricciones/<int:pk>/",
        RestriccionDetailView.as_view(),
        name="restriccion-detail",
    ),
    path(
        "restricciones/<int:pk>/archivar/",
        RestriccionArchivarView.as_view(),
        name="restriccion-archivar",
    ),
    # ── Catálogo de Alimentos ───────────────────────────────
    path("alimentos/", AlimentoListCreateView.as_view(), name="alimento-list-create"),
    path("alimentos/<int:pk>/", AlimentoDetailView.as_view(), name="alimento-detail"),
    path(
        "alimentos/<int:pk>/activar/",
        AlimentoActivarView.as_view(),
        name="alimento-activar",
    ),
    # ── Vinculación Alimento-Restricción ────────────────────
    path(
        "alimentos/<int:pk>/restricciones/",
        AlimentoRestriccionView.as_view(),
        name="alimento-restriccion-list",
    ),
    path(
        "alimentos/<int:pk>/restricciones/<int:rid>/",
        AlimentoRestriccionView.as_view(),
        name="alimento-restriccion-detail",
    ),
    # ── Restricciones del Residente ─────────────────────────
    path(
        "residentes/<int:pk>/restricciones/",
        ResidenteRestriccionView.as_view(),
        name="residente-restriccion-list",
    ),
    path(
        "residentes/<int:pk>/restricciones/<int:rr_id>/revocar/",
        ResidenteRestriccionRevocarView.as_view(),
        name="residente-restriccion-revocar",
    ),
    # GET  /api/residentes/{id}/planes/  → listar todos (T-75)
    # POST /api/residentes/{id}/planes/  → crear con versionado (T-69)
    path(
        "residentes/<int:pk>/planes/",
        PlanListCreateView.as_view(),
        name="plan-list-create",
    ),
    # GET /api/planes/{id}/  → detalle con comidas (T-76)
    path("planes/<int:plan_id>/", PlanDetailView.as_view(), name="plan-detail"),
    # GET  /api/planes/{id}/comidas/  → listar con filtros (T-72)
    # POST /api/planes/{id}/comidas/  → registrar con verificación RF-25 (T-74)
    path(
        "planes/<int:plan_id>/comidas/",
        ComidaListCreateView.as_view(),
        name="comida-list-create",
    ),
    path(
    "comidas/<int:comida_id>/",
    ComidaDetailView.as_view(),
    name="comida-detail",
    ),
]
