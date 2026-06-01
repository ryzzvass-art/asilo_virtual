from django.urls import path
from .views import (
    VisitanteListCreateView,
    AutorizarVisitanteView,
    SuspenderAutorizacionView,
    RegistroVisitaListCreateView,
    RegistroVisitaSalidaView,
    HistorialVisitasResidenteView,
    VisitanteAutorizacionesView,
    ResidenteAutorizacionesView,
)

urlpatterns = [
    # ── Visitantes ──────────────────────────────────────────
    path(
        "visitantes/", VisitanteListCreateView.as_view(), name="visitante-list-create"
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
    # ── Registros de visita ─────────────────────────────────
    path("visitas/", RegistroVisitaListCreateView.as_view(), name="visita-list-create"),
    path(
        "visitas/<int:pk>/salida/",
        RegistroVisitaSalidaView.as_view(),
        name="visita-salida",
    ),
    path(
        "residentes/<int:pk>/visitas/",
        HistorialVisitasResidenteView.as_view(),
        name="historial-visitas",
    ),
    path(
    "visitantes/<int:visitante_id>/autorizaciones/",
    VisitanteAutorizacionesView.as_view(),
    name="visitante-autorizaciones",
),
    path(
    "residentes/<int:residente_id>/autorizaciones/",
    ResidenteAutorizacionesView.as_view(),
    name="residente-autorizaciones",
),
]