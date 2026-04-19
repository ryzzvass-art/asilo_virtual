from rest_framework.routers import DefaultRouter
from usuarios.views import UsuarioViewSet

# El Router genera automáticamente todas las URLs del ViewSet
router = DefaultRouter()
router.register(r'usuarios', UsuarioViewSet, basename='usuarios')

urlpatterns = router.urls