import pytest
from django.contrib.auth import get_user_model

Usuario = get_user_model()


@pytest.mark.django_db
class TestLogin:
    """Pruebas del flujo de login."""

    def test_login_exitoso(self, api_client, admin_user):
        """Login con credenciales válidas devuelve tokens JWT."""
        response = api_client.post('/api/auth/login/', {
            'email': 'admin@test.com',
            'password': 'TestPass123'
        }, format='json')
        assert response.status_code == 200
        assert 'access' in response.data
        assert 'refresh' in response.data
        assert response.data['usuario']['rol'] == 'administrador'

    def test_login_password_incorrecta(self, api_client, admin_user):
        """Login con password incorrecta devuelve 401."""
        response = api_client.post('/api/auth/login/', {
            'email': 'admin@test.com',
            'password': 'WrongPass'
        }, format='json')
        assert response.status_code == 401

    def test_login_usuario_inactivo(self, api_client, admin_user):
        """Usuario inactivo no puede hacer login."""
        admin_user.estado = 'inactivo'
        admin_user.save()
        response = api_client.post('/api/auth/login/', {
            'email': 'admin@test.com',
            'password': 'TestPass123'
        }, format='json')
        assert response.status_code in [400, 401]

    def test_ultimo_login_actualizado(self, api_client, admin_user):
        """El campo ultimo_login se actualiza al hacer login."""
        assert admin_user.ultimo_login is None
        api_client.post('/api/auth/login/', {
            'email': 'admin@test.com',
            'password': 'TestPass123'
        }, format='json')
        admin_user.refresh_from_db()
        assert admin_user.ultimo_login is not None


@pytest.mark.django_db
class TestRefreshToken:
    """Pruebas del token de refresco."""

    def test_refresh_exitoso(self, api_client, admin_user):
        """Refresh token válido genera nuevo access token."""
        login = api_client.post('/api/auth/login/', {
            'email': 'admin@test.com',
            'password': 'TestPass123'
        }, format='json')
        refresh = login.data['refresh']
        response = api_client.post('/api/auth/refresh/', {'refresh': refresh}, format='json')
        assert response.status_code == 200
        assert 'access' in response.data

    def test_refresh_invalido(self, api_client):
        """Refresh token inválido devuelve 401."""
        response = api_client.post('/api/auth/refresh/', {
            'refresh': 'token_invalido'
        }, format='json')
        assert response.status_code == 401


@pytest.mark.django_db
class TestAccesoConToken:
    """Pruebas de acceso a endpoints protegidos."""

    def test_acceso_sin_token(self, api_client):
        """Sin token no se puede acceder a endpoints protegidos."""
        response = api_client.get('/api/residentes/')
        assert response.status_code == 401

    def test_acceso_con_token_admin(self, admin_client):
        """Admin con token válido puede acceder."""
        response = admin_client.get('/api/residentes/')
        assert response.status_code == 200

    def test_cuidador_no_puede_crear_usuario(self, cuidador_client):
        """Cuidador no puede crear usuarios — solo Admin."""
        response = cuidador_client.post('/api/usuarios/', {
            'email': 'nuevo@test.com',
            'nombre': 'Nuevo',
            'apellido': 'Usuario',
            'rol': 'cuidador',
            'password': 'Pass123'
        }, format='json')
        assert response.status_code == 403


@pytest.mark.django_db
class TestRecuperacionPassword:
    """Pruebas del flujo de recuperación de contraseña."""

    def test_solicitar_reset_email_existente(self, api_client, admin_user):
        """Solicitar reset con email existente devuelve 200."""
        response = api_client.post('/api/auth/password-reset/solicitar/', {
            'email': 'admin@test.com'
        }, format='json')
        assert response.status_code == 200

    def test_solicitar_reset_email_inexistente(self, api_client):
        """Solicitar reset con email inexistente también devuelve 200 (seguridad)."""
        response = api_client.post('/api/auth/password-reset/solicitar/', {
            'email': 'noexiste@test.com'
        }, format='json')
        assert response.status_code == 200

    def test_confirmar_token_invalido(self, api_client):
        """Token inválido devuelve 400."""
        import uuid
        response = api_client.post('/api/auth/password-reset/confirmar/', {
            'token': str(uuid.uuid4()),
            'nueva_password': 'NuevoPass123',
            'confirmar_password': 'NuevoPass123'
        }, format='json')
        assert response.status_code == 400

    def test_confirmar_passwords_no_coinciden(self, api_client, admin_user):
        """Passwords que no coinciden devuelven 400."""
        from usuarios.models import PasswordResetToken
        token = PasswordResetToken.objects.create(usuario=admin_user)
        response = api_client.post('/api/auth/password-reset/confirmar/', {
            'token': str(token.token),
            'nueva_password': 'NuevoPass123',
            'confirmar_password': 'Diferente456'
        }, format='json')
        assert response.status_code == 400