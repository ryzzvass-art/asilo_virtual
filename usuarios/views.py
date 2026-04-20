from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from usuarios.serializers import UsuarioSerializer, UsuarioListSerializer, LoginSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from rest_framework.views import APIView


from usuarios.models import Usuario
from usuarios.serializers import UsuarioSerializer, UsuarioListSerializer


class UsuarioViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de usuarios.
    
    Endpoints que genera automáticamente:
    - POST   /api/usuarios/          → crear usuario
    - GET    /api/usuarios/          → listar usuarios
    - GET    /api/usuarios/{id}/     → detalle de usuario
    - PUT    /api/usuarios/{id}/     → editar usuario completo
    - PATCH  /api/usuarios/{id}/     → editar usuario parcial
    - DELETE /api/usuarios/{id}/     → eliminar (no lo usaremos)
    """

    # Qué datos se consultan — solo usuarios activos e inactivos,
    # ordenados por fecha de creación más reciente primero
    queryset = Usuario.objects.all().order_by('-created_at')

    def get_serializer_class(self):
        """
        Usa un serializer diferente según la acción:
        - Si es crear (create) → UsuarioSerializer (con password y validaciones)
        - Para todo lo demás  → UsuarioListSerializer (sin datos sensibles)
        """
        if self.action == 'create':
            return UsuarioSerializer
        return UsuarioListSerializer

    def get_permissions(self):
        """
        Define quién puede hacer qué:
        - Crear usuario: solo administradores autenticados
        - Ver lista y detalle: solo autenticados
        """
        if self.action == 'create':
            # Por ahora AllowAny para poder probar sin token
            # En Sprint 5 lo cambiaremos a IsAuthenticated
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def create(self, request, *args, **kwargs):
        """
        Crea un usuario nuevo.
        Solo el administrador puede hacer esto — lo validaremos
        cuando implementemos JWT en la T-09.
        """
        serializer = UsuarioSerializer(data=request.data)

        if serializer.is_valid():
            usuario = serializer.save()
            return Response(
                {
                    "mensaje": "Usuario creado correctamente.",
                    "usuario": UsuarioListSerializer(usuario).data
                },
                status=status.HTTP_201_CREATED
            )

        # Si hay errores de validación, los devuelve con código 400
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    def list(self, request, *args, **kwargs):
        """
        Lista todos los usuarios.
        Filtro opcional por rol: /api/usuarios/?rol=cuidador
        """
        queryset = self.get_queryset()

        # Filtro por rol si viene en los parámetros de la URL
        rol = request.query_params.get('rol')
        if rol:
            queryset = queryset.filter(rol=rol)

        serializer = UsuarioListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'], url_path='estado')
    def cambiar_estado(self, request, pk=None):
        """
        Endpoint adicional para cambiar estado de un usuario.
        PATCH /api/usuarios/{id}/estado/
        
        Este es el soft delete: en lugar de eliminar,
        cambiamos estado a 'inactivo'.
        """
        usuario = self.get_object()
        nuevo_estado = request.data.get('estado')

        # Validar que el estado sea válido
        estados_validos = [Usuario.Estado.ACTIVO, Usuario.Estado.INACTIVO]
        if nuevo_estado not in estados_validos:
            return Response(
                {"error": "Estado inválido. Use 'activo' o 'inactivo'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        usuario.estado = nuevo_estado
        usuario.save()

        return Response(
            {
                "mensaje": f"Estado actualizado a '{nuevo_estado}'.",
                "usuario": UsuarioListSerializer(usuario).data
            }
        )
    
    

class LoginView(APIView):
    """
    Endpoint de login.
    POST /api/auth/login/
    
    Recibe email y password.
    Devuelve access token, refresh token y datos del usuario.
    """
    # Login no requiere autenticación previa
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        usuario = serializer.validated_data['usuario']

        # Actualizar ultimo_login
        usuario.ultimo_login = timezone.now()
        usuario.save(update_fields=['ultimo_login'])

        # Generar los tokens JWT para este usuario
        refresh = RefreshToken.for_user(usuario)

        return Response({
            "mensaje": f"Bienvenido, {usuario.nombre}.",
            "access":  str(refresh.access_token),
            "refresh": str(refresh),
            "usuario": {
                "id":      usuario.id,
                "nombre":  usuario.nombre,
                "apellido":usuario.apellido,
                "email":   usuario.email,
                "rol":     usuario.rol,
            }
        }, status=status.HTTP_200_OK)