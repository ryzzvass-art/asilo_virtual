from django.urls import path
from .views import (
    AuditLogListView,
    AuditLogDetailView,
    DashboardView,
    ActividadesHoyView,
)

urlpatterns = [
    # ── Audit Log ───────────────────────────────────────────
    path("audit-log/", AuditLogListView.as_view(), name="audit-log-list"),
    path("audit-log/<int:pk>/", AuditLogDetailView.as_view(), name="audit-log-detail"),
    # ── Dashboard ───────────────────────────────────────────
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("actividades/hoy/", ActividadesHoyView.as_view(), name="actividades-hoy"),
]
