from rest_framework.routers import DefaultRouter
from django.urls import path
from usuarios.views import UsuarioViewSet
from .views import SolicitarPasswordResetView
from .views import ConfirmarPasswordResetView
from .views import UsuarioEstadoView
from rest_framework_simplejwt.views import  TokenRefreshView
from .views import CustomTokenObtainPairView

router = DefaultRouter()
router.register(r"usuarios", UsuarioViewSet, basename="usuarios")

# Combinamos las URLs del router con las adicionales
urlpatterns = [
    path("auth/login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path(
        "auth/password-reset/solicitar/",
        SolicitarPasswordResetView.as_view(),
        name="password-reset-solicitar",
    ),
    path(
        "auth/password-reset/confirmar/",
        ConfirmarPasswordResetView.as_view(),
        name="password-reset-confirmar",
    ),
    path(
        "usuarios/<int:pk>/estado/", UsuarioEstadoView.as_view(), name="usuario-estado"
    ),
] + router.urls
