from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
#resete token
import uuid
from django.utils import timezone
from datetime import timedelta

# ── MANAGER ──────────────────────────────────────────────────────────────────
# El Manager es el que sabe cómo CREAR usuarios.
# Django lo necesita cuando usás AbstractBaseUser.

class UsuarioManager(BaseUserManager):

    def create_user(self, email, nombre, apellido, rol, password=None):
        # Validar que el email no esté vacío
        if not email:
            raise ValueError("El email es obligatorio.")
        
        # Normalizar el email (convierte mayúsculas a minúsculas)
        email = self.normalize_email(email)
        
        # Crear la instancia del usuario con los datos
        usuario = self.model(
            email=email,
            nombre=nombre,
            apellido=apellido,
            rol=rol,
        )
        
        # Guardar la contraseña encriptada (nunca en texto plano)
        usuario.set_password(password)
        
        # Guardar en la base de datos
        usuario.save(using=self._db)
        return usuario

    def create_superuser(self, email, nombre, apellido, password=None):
        # El superusuario siempre es administrador
        return self.create_user(
            email=email,
            nombre=nombre,
            apellido=apellido,
            rol=Usuario.Rol.ADMINISTRADOR,
            password=password,
        )


# ── MODELO USUARIO ────────────────────────────────────────────────────────────

class Usuario(AbstractBaseUser, PermissionsMixin):
    """
    Usuario del sistema. Reemplaza al User de Django por defecto.
    Roles: administrador | cuidador
    Soft delete: estado 'inactivo' en lugar de eliminar el registro.
    """

    # Opciones de rol — TextChoices crea las opciones válidas
    class Rol(models.TextChoices):
        ADMINISTRADOR = "administrador", "Administrador"
        CUIDADOR      = "cuidador",      "Cuidador"

    # Opciones de estado
    class Estado(models.TextChoices):
        ACTIVO   = "activo",   "Activo"
        INACTIVO = "inactivo", "Inactivo"

    # ── CAMPOS DE LA TABLA ────────────────────────────────────────────────────
    nombre       = models.CharField(max_length=100)
    apellido     = models.CharField(max_length=100)
    
    # unique=True significa que no puede haber dos usuarios con el mismo email
    email        = models.EmailField(unique=True)
    
    rol          = models.CharField(
        max_length=20,
        choices=Rol.choices,
    )
    estado       = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.ACTIVO,       # Por defecto todo usuario empieza activo
    )
    
    # null=True significa que puede estar vacío en la BD
    # blank=True significa que el formulario no lo requiere
    ultimo_login = models.DateTimeField(null=True, blank=True)
    
    # auto_now_add=True guarda automáticamente la fecha de creación
    created_at   = models.DateTimeField(auto_now_add=True)

    # Campos requeridos por Django internamente
    is_active  = models.BooleanField(default=True)
    is_staff   = models.BooleanField(default=False)

    # Le decimos a Django que use email en lugar de username para login
    USERNAME_FIELD  = "email"
    
    # Campos obligatorios al crear superusuario por terminal
    REQUIRED_FIELDS = ["nombre", "apellido", "rol"]

    # Conectar el Manager que creamos arriba
    objects = UsuarioManager()

    # ── CONFIGURACIÓN DE LA TABLA ─────────────────────────────────────────────
    class Meta:
        db_table = "usuarios"   # Nombre exacto de la tabla en PostgreSQL
        indexes = [
            # Índices para acelerar búsquedas frecuentes
            models.Index(fields=["rol"],    name="idx_usuarios_rol"),
            models.Index(fields=["estado"], name="idx_usuarios_estado"),
        ]

    # Representación en texto del objeto (útil para debugging)
    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.rol})"

    # Propiedades útiles para verificar rol fácilmente
    @property
    def es_administrador(self):
        return self.rol == self.Rol.ADMINISTRADOR

    @property
    def es_cuidador(self):
        return self.rol == self.Rol.CUIDADOR
    

class PasswordResetToken(models.Model):
    """
    Tokens temporales para recuperación de contraseña.
    - Cada token es un UUID único
    - Expira 1 hora después de ser creado
    - Una vez usado, no puede reutilizarse (campo 'usado')
    - Al pedir nuevo token, los anteriores del usuario se invalidan (ver T-13)
    """
 
    usuario = models.ForeignKey(
        'Usuario',                      # FK → usuarios.id
        on_delete=models.CASCADE,       # Si se borra el usuario, se borran sus tokens
        related_name='reset_tokens'
    )
    token = models.UUIDField(
        default=uuid.uuid4,             # Genera UUID aleatorio automáticamente
        unique=True,                    # No puede repetirse en toda la tabla
        editable=False
    )
    expira_en = models.DateTimeField()  # Se calcula en save(): created_at + 1 hora
    usado = models.BooleanField(
        default=False                   # True = ya fue utilizado, no se puede reusar
    )
 
    class Meta:
        db_table = 'password_reset_tokens'
        verbose_name = 'Token de recuperación'
        verbose_name_plural = 'Tokens de recuperación'
 
    def save(self, *args, **kwargs):
        # Si es un token nuevo (sin pk), calcular expiración = ahora + 1 hora
        if not self.pk:
            self.expira_en = timezone.now() + timedelta(hours=1)
        super().save(*args, **kwargs)
 
    def is_valid(self):
        """
        Retorna True si el token es usable:
        - No fue usado todavía
        - No expiró (expira_en > ahora)
        """
        return not self.usado and self.expira_en > timezone.now()
 
    def __str__(self):
        return f"Token de {self.usuario.email} — {'usado' if self.usado else 'activo'}"