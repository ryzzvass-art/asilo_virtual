from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from usuarios.serializers import (
    UsuarioSerializer,
    UsuarioListSerializer,
    LoginSerializer,
)
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from rest_framework.views import APIView
from usuarios.permissions import IsAdministrador, IsAdminOrCuidador
from django.core.mail import send_mail
from django.conf import settings
from .models import Usuario, PasswordResetToken
from .serializers import SolicitarResetSerializer
from .serializers import ConfirmarResetSerializer
from .serializers import CambiarEstadoUsuarioSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer
from auditoria.mixins import AuditLogMixin, serializar_instancia


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
    queryset = Usuario.objects.all().order_by("-created_at")

    def get_serializer_class(self):
        """
        Usa un serializer diferente según la acción:
        - Si es crear (create) → UsuarioSerializer (con password y validaciones)
        - Para todo lo demás  → UsuarioListSerializer (sin datos sensibles)
        """
        if self.action == "create":
            return UsuarioSerializer
        return UsuarioListSerializer

    def get_permissions(self):
        """
        Define quién puede hacer qué en cada acción:
        - Crear usuario:         solo Administrador
        - Listar usuarios:       solo Administrador
        - Ver detalle:           Administrador o Cuidador
        - Cambiar estado:        solo Administrador
        """
        if self.action in ["create", "list", "cambiar_estado"]:
            permission_classes = [IsAdministrador]
        else:
            permission_classes = [IsAdminOrCuidador]
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
                    "usuario": UsuarioListSerializer(usuario).data,
                },
                status=status.HTTP_201_CREATED,
            )

        # Si hay errores de validación, los devuelve con código 400
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def list(self, request, *args, **kwargs):
        """
        Lista todos los usuarios.
        Filtro opcional por rol: /api/usuarios/?rol=cuidador
        """
        queryset = self.get_queryset()

        # Filtro por rol si viene en los parámetros de la URL
        rol = request.query_params.get("rol")
        if rol:
            queryset = queryset.filter(rol=rol)

        serializer = UsuarioListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["patch"], url_path="estado")
    def cambiar_estado(self, request, pk=None):
        """
        Endpoint adicional para cambiar estado de un usuario.
        PATCH /api/usuarios/{id}/estado/

        Este es el soft delete: en lugar de eliminar,
        cambiamos estado a 'inactivo'.
        """
        usuario = self.get_object()
        nuevo_estado = request.data.get("estado")

        # Validar que el estado sea válido
        estados_validos = [Usuario.Estado.ACTIVO, Usuario.Estado.INACTIVO]
        if nuevo_estado not in estados_validos:
            return Response(
                {"error": "Estado inválido. Use 'activo' o 'inactivo'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        usuario.estado = nuevo_estado
        usuario.save()

        return Response(
            {
                "mensaje": f"Estado actualizado a '{nuevo_estado}'.",
                "usuario": UsuarioListSerializer(usuario).data,
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
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        usuario = serializer.validated_data["usuario"]

        # Actualizar ultimo_login
        usuario.ultimo_login = timezone.now()
        usuario.save(update_fields=["ultimo_login"])

        # Generar los tokens JWT para este usuario
        refresh = RefreshToken.for_user(usuario)

        return Response(
            {
                "mensaje": f"Bienvenido, {usuario.nombre}.",
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "usuario": {
                    "id": usuario.id,
                    "nombre": usuario.nombre,
                    "apellido": usuario.apellido,
                    "email": usuario.email,
                    "rol": usuario.rol,
                },
            },
            status=status.HTTP_200_OK,
        )


# reset paswword


class SolicitarPasswordResetView(APIView):
    """
    POST /api/auth/password-reset/solicitar/

    Qué hace:
    1. Recibe el email
    2. Busca el usuario
    3. Invalida tokens anteriores del mismo usuario
    4. Crea un nuevo token
    5. Envía el email con el enlace de recuperación

    Seguridad: siempre devuelve 200, aunque el email no exista
    (para no revelar qué emails están registrados)
    """

    permission_classes = [AllowAny]  # No requiere estar autenticado

    def post(self, request):
        serializer = SolicitarResetSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"]

        # Buscar usuario (puede no existir — ver nota de seguridad abajo)
        try:
            usuario = Usuario.objects.get(email=email, estado="activo")
        except Usuario.DoesNotExist:
            # SEGURIDAD: no revelamos que el email no existe
            # Respondemos igual que si hubiera funcionado
            return Response(
                {
                    "mensaje": "Si el email está registrado, recibirás un enlace en minutos."
                },
                status=status.HTTP_200_OK,
            )

        # Invalidar todos los tokens anteriores de este usuario
        # (evita que haya múltiples tokens válidos al mismo tiempo)
        PasswordResetToken.objects.filter(usuario=usuario, usado=False).update(
            usado=True
        )

        # Crear nuevo token (expira_en se calcula automáticamente en save())
        nuevo_token = PasswordResetToken.objects.create(usuario=usuario)

        # Construir el enlace de recuperación
        # En producción: usar settings.FRONTEND_URL
        # En desarrollo: ajusta la URL según tu frontend
        reset_link = f"http://localhost:3000/reset-password?token={nuevo_token.token}"

        # Enviar email
        send_mail(
            subject="Recuperación de contraseña — Asilo Virtual",
            message=f"""
Hola {usuario.nombre},
 
Recibiste este email porque solicitaste recuperar tu contraseña.
 
Haz clic en el siguiente enlace (válido por 1 hora):
{reset_link}
 
Si no solicitaste esto, ignora este mensaje.
 
— Sistema Asilo Virtual
            """,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[usuario.email],
            fail_silently=False,
        )

        return Response(
            {"mensaje": "Si el email está registrado, recibirás un enlace en minutos."},
            status=status.HTTP_200_OK,
        )


class ConfirmarPasswordResetView(APIView):
    """
    POST /api/auth/password-reset/confirmar/

    Qué hace:
    1. Recibe el token y la nueva contraseña
    2. Busca el token en la base de datos
    3. Verifica que sea válido (no expirado, no usado)
    4. Actualiza la contraseña del usuario
    5. Marca el token como usado=True (no se puede reusar)

    Errores posibles:
    - Token no existe → 400
    - Token expirado  → 400
    - Token ya usado  → 400
    - Passwords no coinciden → 400
    """

    permission_classes = [AllowAny]  # No requiere estar autenticado

    def post(self, request):
        serializer = ConfirmarResetSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        token_uuid = serializer.validated_data["token"]
        nueva_password = serializer.validated_data["nueva_password"]

        # Buscar el token en la base de datos
        try:
            reset_token = PasswordResetToken.objects.select_related("usuario").get(
                token=token_uuid
            )
        except PasswordResetToken.DoesNotExist:
            return Response(
                {"error": "Token inválido o no existe."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verificar que el token sea válido (no expirado y no usado)
        if not reset_token.is_valid():
            if reset_token.usado:
                mensaje = "Este enlace ya fue utilizado. Solicita uno nuevo."
            else:
                mensaje = "Este enlace expiró (validez: 1 hora). Solicita uno nuevo."

            return Response({"error": mensaje}, status=status.HTTP_400_BAD_REQUEST)

        # Token válido → actualizar contraseña
        usuario = reset_token.usuario
        usuario.set_password(
            nueva_password
        )  # set_password encripta con bcrypt automáticamente
        usuario.save()

        # Marcar el token como usado para que no pueda reutilizarse
        reset_token.usado = True
        reset_token.save()

        return Response(
            {
                "mensaje": "Contraseña actualizada correctamente. Ya puedes iniciar sesión."
            },
            status=status.HTTP_200_OK,
        )


class UsuarioEstadoView(AuditLogMixin, APIView):
    # A1-declarar auditoria
    audit_entidad = "usuarios"

    permission_classes = [IsAdministrador]  # Tu permiso personalizado del T-09

    def patch(self, request, pk):
        # Obtener el usuario que se quiere modificar
        try:
            usuario = Usuario.objects.get(pk=pk)
        except Usuario.DoesNotExist:
            return Response(
                {"error": "Usuario no encontrado."}, status=status.HTTP_404_NOT_FOUND
            )
       # A2 - Snapshot antes de modificar
        antes = serializar_instancia(usuario)
        # Seguridad: un admin no puede desactivarse a sí mismo
        if request.user.pk == usuario.pk:
            return Response(
                {"error": "No puedes cambiar tu propio estado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CambiarEstadoUsuarioSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        nuevo_estado = serializer.validated_data["estado"]

        # Actualizar solo el campo estado (no toca otros campos)
        usuario.estado = nuevo_estado
        usuario.save(update_fields=["estado"])

        # A3 - Registrar auditoría
        self.audit_editar(request, antes, usuario)

        return Response(
            {
                "mensaje": f"Usuario {'activado' if nuevo_estado == 'activo' else 'desactivado'} correctamente.",
                "id": usuario.pk,
                "email": usuario.email,
                "estado": usuario.estado,
            },
            status=status.HTTP_200_OK,
        )


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Vista de login personalizada que usa nuestro serializer extendido.
    Reemplaza la vista por defecto de SimpleJWT.
    """

    serializer_class = CustomTokenObtainPairSerializer
