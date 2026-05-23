from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api-auth/", include("rest_framework.urls")),
    path("api/", include("usuarios.urls")),
    path("api/", include("residentes.urls")),
    path("api/", include("medicamentos.urls")),
    path("api/", include("nutricion.urls")),
    path("api/", include("actividades.urls")),
    path("api/", include("visitas.urls")),
    path('api/', include('auditoria.urls')),
]
