from rest_framework.routers import DefaultRouter
from django.urls import path
from usuarios.views import UsuarioViewSet, LoginView
from rest_framework_simplejwt.views import TokenRefreshView

router = DefaultRouter()
router.register(r'usuarios', UsuarioViewSet, basename='usuarios')

# Combinamos las URLs del router con las adicionales
urlpatterns = [
    path('auth/login/',   LoginView.as_view(),       name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
] + router.urls