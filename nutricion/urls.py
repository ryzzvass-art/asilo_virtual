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
    PlanListView,
    PlanDetailView,
    ComidaListCreateView,
    ComidaDetailView,
    PlantillaListCreateView,    
    PlantillaDetailView,        
    PlantillaAprobarView,       
    PlantillaRechazarView,      
    AsignarPlantillaView,
    PlantillaEditarView,
    AlimentoArchivarView,
    RestriccionActivarView,
    NutricionResumenView,
    PlantillaAsignadosView
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
    path(
    'restricciones/<int:pk>/activar/',
    RestriccionActivarView.as_view(),
    name='restriccion-activar',
    ),
    # ── Planes del residente (legacy) ───────────────────────
    path(
        "residentes/<int:pk>/planes/",
        PlanListView.as_view(),
        name="plan-list-create",
    ),
    # ── Asignar plantilla aprobada a residente (nuevo) ──────
    path(
        "residentes/<int:pk>/planes/asignar/",
        AsignarPlantillaView.as_view(),
        name="plan-asignar-plantilla",
    ),
    # ── Detalle y comidas de un plan ────────────────────────
    path("planes/<int:plan_id>/", PlanDetailView.as_view(), name="plan-detail"),
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
    # ── Plantillas Nutricionales (nuevo) ────────────────────
    path(
        "plantillas/",
        PlantillaListCreateView.as_view(),
        name="plantilla-list-create",
    ),
    path(
        "plantillas/<int:pk>/",
        PlantillaDetailView.as_view(),
        name="plantilla-detail",
    ),
    path(
        "plantillas/<int:pk>/asignados/",
        PlantillaAsignadosView.as_view(),
        name="plantilla-asignados",
    ),
    path(
        "plantillas/<int:pk>/aprobar/",
        PlantillaAprobarView.as_view(),
        name="plantilla-aprobar",
    ),
    path(
        "plantillas/<int:pk>/rechazar/",
        PlantillaRechazarView.as_view(),
        name="plantilla-rechazar",
    ),
    path(
    'plantillas/<int:pk>/editar/',
    PlantillaEditarView.as_view(),
    name='plantilla-editar',
    ),
    path(
    'alimentos/<int:pk>/archivar/',
    AlimentoArchivarView.as_view(),
    name='alimento-archivar',
    ),
    path(
        'nutricion/resumen-dashboard/',
        NutricionResumenView.as_view(),
        name='nutricion-resumen-dashboard',
    ),
]