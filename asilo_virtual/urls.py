from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView


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
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
