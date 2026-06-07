from django.urls import path
from .views import (
    VisitanteListCreateView,
    VisitanteDetailView,
    AutorizarVisitanteView,
    SuspenderAutorizacionView,
    RegistroVisitaListCreateView,
    RegistroVisitaSalidaView,
    HistorialVisitasResidenteView,
    VisitanteAutorizacionesView,
    ResidenteAutorizacionesView,
    ResumenDashboardVisitasView,
)

urlpatterns = [
    # ── Visitantes ──────────────────────────────────────────
    path(
        "visitantes/", VisitanteListCreateView.as_view(), name="visitante-list-create"
    ),
    path(
        "visitantes/<int:pk>/",
        VisitanteDetailView.as_view(),
        name="visitante-detail",
    ),
    path(
        "visitantes/<int:visitante_id>/autorizar/<int:residente_id>/",
        AutorizarVisitanteView.as_view(),
        name="autorizar-visitante",
    ),
    path(
        "visitantes/<int:visitante_id>/autorizar/<int:residente_id>/suspender/",
        SuspenderAutorizacionView.as_view(),
        name="suspender-autorizacion",
    ),
    path(
        "visitantes/<int:visitante_id>/autorizaciones/",
        VisitanteAutorizacionesView.as_view(),
        name="visitante-autorizaciones",
    ),
    # ── Registros de visita ─────────────────────────────────
    path("visitas/", RegistroVisitaListCreateView.as_view(), name="visita-list-create"),
    path(
        "visitas/<int:pk>/salida/",
        RegistroVisitaSalidaView.as_view(),
        name="visita-salida",
    ),
    path(
        "visitas/resumen-dashboard/",
        ResumenDashboardVisitasView.as_view(),
        name="visitas-resumen-dashboard",
    ),
    # ── Autorizaciones / historial por residente ────────────
    path(
        "residentes/<int:pk>/visitas/",
        HistorialVisitasResidenteView.as_view(),
        name="historial-visitas",
    ),
    path(
        "residentes/<int:residente_id>/autorizaciones/",
        ResidenteAutorizacionesView.as_view(),
        name="residente-autorizaciones",
    ),
]
