
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

Usuario = get_user_model()


@pytest.fixture
def api_client():
    """Cliente API sin autenticar."""
    return APIClient()


@pytest.fixture
def admin_user(db):
    user = Usuario.objects.create_user(
        email='admin@test.com',
        nombre='Admin',
        apellido='Test',
        rol='administrador',
        password='TestPass123'
    )
    user.is_active = True    # ← agregar
    user.is_staff = True          # ← Agregar
    user.is_superuser = True
    user.save()
    return user



@pytest.fixture
def cuidador_user(db):
    user = Usuario.objects.create_user(
        email='cuidador@test.com',
        nombre='Cuidador',
        apellido='Test',
        rol='cuidador',
        password='TestPass123'
    )
    user.is_active = True    # ← agregar
    user.save()
    return user


@pytest.fixture
def admin_client(api_client, admin_user):
    """Cliente API autenticado como administrador."""
    client = APIClient()                    # ← Crear un cliente nuevo
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def cuidador_client(api_client, cuidador_user):
    """Cliente API autenticado como cuidador."""
    client = APIClient()                    # ← Crear un cliente nuevo
    client.force_authenticate(user=cuidador_user)
    return client

