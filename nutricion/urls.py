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
]
