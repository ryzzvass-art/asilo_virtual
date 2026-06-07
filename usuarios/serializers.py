from rest_framework import serializers
from usuarios.models import Usuario
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.utils import timezone


class UsuarioSerializer(serializers.ModelSerializer):
    """
    Serializer para crear y listar usuarios.
    Maneja la conversión entre objeto Usuario y JSON.
    """

    # El password se escribe pero nunca se devuelve en las respuestas
    # write_only=True significa: acepta el valor al crear, pero no lo incluye
    # en el JSON de respuesta
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        error_messages={
            "min_length": "La contraseña debe tener al menos 8 caracteres."
        },
    )

    class Meta:
        # Le decimos qué modelo representa este serializer
        model = Usuario

        # Los campos que van a aparecer en el JSON
        fields = [
            "id",
            "nombre",
            "apellido",
            "email",
            "password",
            "rol",
            "estado",
            "ultimo_login",
            "created_at",
        ]

        # Campos que solo se leen, no se pueden modificar desde el frontend
        read_only_fields = ["id", "estado", "ultimo_login", "created_at"]

    def validate_email(self, value):
        """
        Verifica que el email no esté registrado ya en la BD.
        Django llama automáticamente a validate_<campo> si existe.
        """
        # Convertir a minúsculas para evitar duplicados como
        # Juan@gmail.com y juan@gmail.com
        value = value.lower()

        # Verificar si ya existe un usuario con ese email
        if Usuario.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "Ya existe un usuario registrado con este email."
            )
        return value

    def validate_rol(self, value):
        """
        Verifica que el rol sea uno de los valores permitidos.
        """
        roles_validos = [Usuario.Rol.ADMINISTRADOR, Usuario.Rol.CUIDADOR]
        if value not in roles_validos:
            raise serializers.ValidationError(
                f"Rol inválido. Debe ser 'administrador' o 'cuidador'."
            )
        return value

    def create(self, validated_data):
        """
        Crea el usuario usando el Manager personalizado.
        Esto garantiza que la contraseña se encripte correctamente.
        """
        # Extraer el password del diccionario de datos validados
        password = validated_data.pop("password")

        # Crear el usuario con todos los datos menos el password
        usuario = Usuario(**validated_data)

        # Encriptar y guardar el password por separado
        usuario.set_password(password)
        usuario.save()

        return usuario


class UsuarioListSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para listar usuarios.
    No incluye datos sensibles como password ni ultimo_login.
    """

    class Meta:
        model = Usuario
        fields = [
            "id",
            "nombre",
            "apellido",
            "email",
            "rol",
            "estado",
            "created_at",
        ]
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    """
    Serializer para el login.
    Recibe email y password, valida las credenciales
    y devuelve los tokens JWT.
    """

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get("email").lower()
        password = data.get("password")

        # Buscar el usuario por email
        try:
            usuario = Usuario.objects.get(email=email)
        except Usuario.DoesNotExist:
            raise serializers.ValidationError("Credenciales inválidas.")

        # Verificar que la contraseña sea correcta
        if not usuario.check_password(password):
            raise serializers.ValidationError("Credenciales inválidas.")

        # Verificar que el usuario esté activo
        if usuario.estado == Usuario.Estado.INACTIVO:
            raise serializers.ValidationError(
                "Cuenta deshabilitada. Contacte al administrador."
            )

        # Guardar el usuario en los datos validados
        # para usarlo después en la vista
        data["usuario"] = usuario
        return data


class SolicitarResetSerializer(serializers.Serializer):
    """
    Solo necesita el email del usuario.
    Valida que el email exista en la base de datos.
    """

    email = serializers.EmailField()

    def validate_email(self, value):
        # Convertir a minúsculas para evitar problemas de mayúsculas
        value = value.lower()
        # Verificar que exista un usuario con ese email
        if not Usuario.objects.filter(email=value, estado="activo").exists():
            # SEGURIDAD: no revelamos si el email existe o no
            # Retornamos el email igual para procesar en la vista
            pass
        return value


class ConfirmarResetSerializer(serializers.Serializer):
    """
    Recibe el token UUID y la nueva contraseña.
    Valida que la nueva contraseña tenga al menos 8 caracteres.
    """

    token = serializers.UUIDField()
    nueva_password = serializers.CharField(
        min_length=8, write_only=True  # Nunca se devuelve en la respuesta
    )
    confirmar_password = serializers.CharField(min_length=8, write_only=True)

    def validate(self, data):
        # Verificar que las dos contraseñas coincidan
        if data["nueva_password"] != data["confirmar_password"]:
            raise serializers.ValidationError(
                {"confirmar_password": "Las contraseñas no coinciden."}
            )
        return data


class CambiarEstadoUsuarioSerializer(serializers.Serializer):
    """
    Solo acepta los dos valores válidos para estado de usuario.
    """

    estado = serializers.ChoiceField(choices=["activo", "inactivo"])


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extiende el serializer de SimpleJWT para agregar
    la verificación de estado del usuario.

    Si el usuario existe y la contraseña es correcta PERO
    el estado es 'inactivo', rechaza con 401.
    """

    def validate(self, attrs):
        # Primero ejecuta la validación normal de SimpleJWT
        # (verifica email + contraseña)
        try:
            data = super().validate(attrs)
        except Exception:
            # Si falla autenticación normal, dejar que SimpleJWT maneje el error
            raise

        # En este punto, self.user ya tiene el usuario autenticado
        # Ahora verificamos el estado adicional
        if self.user.estado == "inactivo":
            raise serializers.ValidationError(
                {"detail": "Cuenta deshabilitada. Contacta al administrador."}
            )
        self.user.ultimo_login = timezone.now()
        self.user.save(update_fields=["ultimo_login"])

        # Opcional: agregar datos extra al token o a la respuesta
        data["usuario"] = {
            "id": self.user.pk,
            "nombre": self.user.nombre,
            "apellido": self.user.apellido,
            "email": self.user.email,
            "rol": self.user.rol,
        }

        return data
class UsuarioUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer para EDITAR usuarios (PUT/PATCH).

    - 'password' es opcional y write_only. Si viene, se re-encripta.
    - 'email' valida unicidad excluyendo al propio usuario.
    - La lógica de "a un cuidador no se le cambia el password" y
      "un admin no cambia su propio rol" se aplica en la vista,
      porque depende de QUIÉN edita a QUIÉN (contexto del request).
    """

    password = serializers.CharField(
        write_only=True,
        required=False,        # opcional: editar sin tocar la contraseña
        allow_blank=True,      # si llega vacío, lo ignoramos en update()
        min_length=8,
        error_messages={
            "min_length": "La contraseña debe tener al menos 8 caracteres."
        },
    )

    class Meta:
        model = Usuario
        fields = ["id", "nombre", "apellido", "email", "password", "rol", "estado"]
        # 'estado' sigue gestionándose por su endpoint dedicado (soft delete),
        # así que lo dejamos de solo lectura aquí para no duplicar caminos.
        read_only_fields = ["id", "estado"]

    def validate_email(self, value):
        value = value.lower()
        # Excluir al propio usuario de la verificación de duplicados,
        # si no, editar sin cambiar el email daría "ya existe".
        qs = Usuario.objects.filter(email=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "Ya existe un usuario registrado con este email."
            )
        return value

    def validate_rol(self, value):
        roles_validos = [Usuario.Rol.ADMINISTRADOR, Usuario.Rol.CUIDADOR]
        if value not in roles_validos:
            raise serializers.ValidationError(
                "Rol inválido. Debe ser 'administrador' o 'cuidador'."
            )
        return value

    def update(self, instance, validated_data):
        # Sacamos el password para tratarlo aparte (encriptado).
        password = validated_data.pop("password", None)

        # Actualizamos el resto de campos normalmente.
        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)

        # Solo cambiamos la contraseña si vino con contenido real.
        if password:
            instance.set_password(password)

        instance.save()
        return instance