from django.urls import path
from .views import (
    VisitanteListCreateView,
    AutorizarVisitanteView,
    SuspenderAutorizacionView,
    RegistroVisitaListCreateView,
    RegistroVisitaSalidaView,
    HistorialVisitasResidenteView,
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
]
