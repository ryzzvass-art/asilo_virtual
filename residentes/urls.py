# ============================================================
# SPRINT 2 — URLs
# Archivo NUEVO: residentes/urls.py
# ============================================================

from django.urls import path
from .views import (
    ResidenteListCreateView,
    ResidenteDetailView,
    ResidenteEstadoView,
    ContactoEmergenciaView,
    ContactoEmergenciaDetailView,
    HistorialMedicoView,
)

urlpatterns = [
    # ── Residentes ──────────────────────────────────────────
    # GET  /api/residentes/        → listar con filtros (T-20)
    # POST /api/residentes/        → crear residente   (T-19)
    path('residentes/', ResidenteListCreateView.as_view(), name='residente-list-create'),

    # GET   /api/residentes/{id}/  → detalle completo (T-21)
    # PUT   /api/residentes/{id}/  → edición total    (T-22)
    # PATCH /api/residentes/{id}/  → edición parcial  (T-22)
    path('residentes/<int:pk>/', ResidenteDetailView.as_view(), name='residente-detail'),

    # PATCH /api/residentes/{id}/estado/  → cambiar estado (T-23)
    path('residentes/<int:pk>/estado/', ResidenteEstadoView.as_view(), name='residente-estado'),

    # ── Contactos de emergencia ─────────────────────────────
    # GET  /api/residentes/{id}/contactos/        → listar (T-25)
    # POST /api/residentes/{id}/contactos/        → crear  (T-24)
    path('residentes/<int:pk>/contactos/', ContactoEmergenciaView.as_view(), name='contacto-list-create'),

    # PATCH  /api/residentes/{id}/contactos/{cid}/ → editar  (T-25)
    # DELETE /api/residentes/{id}/contactos/{cid}/ → eliminar(T-25)
    path('residentes/<int:pk>/contactos/<int:cid>/', ContactoEmergenciaDetailView.as_view(), name='contacto-detail'),

    # ── Historial médico ────────────────────────────────────
    # GET   /api/residentes/{id}/historial/ → ver     (T-26)
    # PATCH /api/residentes/{id}/historial/ → editar  (T-27)
    path('residentes/<int:pk>/historial/', HistorialMedicoView.as_view(), name='historial-detail'),
]
