
from django.urls import path
from .views import (
    ResidenteListCreateView,
    ResidenteDetailView,
    ResidenteEstadoView,
    ContactoEmergenciaView,
    ContactoEmergenciaDetailView,
    HistorialMedicoView,
    ObservacionListCreateView,
    ObservacionDetailView,
    TurnoMedicoListCreateView,
    TurnoMedicoDetailView,
    ResumenDashboardResidentesView, 
)

urlpatterns = [
    
    path(
        "residentes/", ResidenteListCreateView.as_view(), name="residente-list-create"
    ),
    path(
        "residentes/resumen-dashboard/",
        ResumenDashboardResidentesView.as_view(),
        name="residentes-resumen-dashboard",
    ),
    path("residentes/<int:pk>/", ResidenteDetailView.as_view(), name="residente-detail"),
    # PATCH /api/residentes/{id}/estado/  → cambiar estado (T-23)
    path(
        "residentes/<int:pk>/estado/",
        ResidenteEstadoView.as_view(),
        name="residente-estado",
    ),
    # ── Contactos de emergencia ─────────────────────────────
    # GET  /api/residentes/{id}/contactos/        → listar (T-25)
    # POST /api/residentes/{id}/contactos/        → crear  (T-24)
    path(
        "residentes/<int:pk>/contactos/",
        ContactoEmergenciaView.as_view(),
        name="contacto-list-create",
    ),
    # PATCH  /api/residentes/{id}/contactos/{cid}/ → editar  (T-25)
    # DELETE /api/residentes/{id}/contactos/{cid}/ → eliminar(T-25)
    path(
        "residentes/<int:pk>/contactos/<int:cid>/",
        ContactoEmergenciaDetailView.as_view(),
        name="contacto-detail",
    ),
    # ── Historial médico ────────────────────────────────────
    # GET   /api/residentes/{id}/historial/ → ver     (T-26)
    # PATCH /api/residentes/{id}/historial/ → editar  (T-27)
    path(
        "residentes/<int:pk>/historial/",
        HistorialMedicoView.as_view(),
        name="historial-detail",
    ),
    #     # ── Observaciones diarias ───────────────────────────────
    # GET  /api/residentes/{id}/observaciones/              # listar (T-32)
    # POST /api/residentes/{id}/observaciones/              # crear  (T-30)
    path(
        "residentes/<int:pk>/observaciones/",
        ObservacionListCreateView.as_view(),
        name="observacion-list-create",
    ),
    # GET /api/residentes/{id}/observaciones/{obs_id}/       #detalle (ST-31)
    path(
        "residentes/<int:pk>/observaciones/<int:obs_id>/",
        ObservacionDetailView.as_view(),
        name="observacion-detail",
    ),
    # ── Turnos médicos ─────────────────────────────────────
    # GET  /api/residentes/{id}/turnos/                     # listar (T-36)
    # POST /api/residentes/{id}/turnos/                      # crear  (T-35)
    path(
        "residentes/<int:pk>/turnos/",
        TurnoMedicoListCreateView.as_view(),
        name="turno-list-create",
    ),
    # PATCH /api/residentes/{id}/turnos/{turno_id}/  → editar (solo admin)
    path(
        "residentes/<int:pk>/turnos/<int:turno_id>/",
        TurnoMedicoDetailView.as_view(),
        name="turno-detail",
    ),
]
