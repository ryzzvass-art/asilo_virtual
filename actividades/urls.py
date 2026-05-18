from django.urls import path
from .views import (
    ActividadListCreateView,
    ActividadDetailView,
    ActividadCancelarView,
    ActividadResidenteView,
)

urlpatterns = [
    path(
        "actividades/", ActividadListCreateView.as_view(), name="actividad-list-create"
    ),
    path(
        "actividades/<int:pk>/", ActividadDetailView.as_view(), name="actividad-detail"
    ),
    path(
        "actividades/<int:pk>/cancelar/",
        ActividadCancelarView.as_view(),
        name="actividad-cancelar",
    ),
    path(
        "actividades/<int:pk>/residentes/",
        ActividadResidenteView.as_view(),
        name="actividad-residentes",
    ),
    path(
        "actividades/<int:pk>/residentes/<int:residente_id>/",
        ActividadResidenteView.as_view(),
        name="actividad-residente-detail",
    ),
]
