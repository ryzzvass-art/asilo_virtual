import pytest
from django.contrib.auth import get_user_model
from auditoria.models import AuditLog
from auditoria.mixins import registrar_auditoria, serializar_instancia
from residentes.models import Residente

Usuario = get_user_model()


@pytest.mark.django_db
class TestAuditLog:

    def test_audit_log_se_crea_al_crear_residente(
        self, admin_client, admin_user
    ):
        """Crear residente genera entrada en audit_log."""
        response = admin_client.post('/api/residentes/', {
            'nombre': 'Test',
            'apellido': 'Residente',
            'dni': '99999999',
            'fecha_nacimiento': '1950-01-01',
            'fecha_ingreso': '2026-01-01',
        }, format='json')
        assert response.status_code == 201
        # Verificar que se creó el log
        assert AuditLog.objects.filter(
            entidad='residentes',
            accion='crear'
        ).exists()

    def test_audit_log_solo_admin(self, admin_client, cuidador_client):
        # Cuidador debe dar 403
        response = cuidador_client.get('/api/audit-log/')
        assert response.status_code == 403

        # Admin debe dar 200
        response = admin_client.get('/api/audit-log/')
        assert response.status_code == 200

    def test_audit_log_filtro_por_entidad(self, admin_client, admin_user):
        """Filtro por entidad funciona correctamente."""
        AuditLog.objects.create(
            usuario=admin_user,
            accion='crear',
            entidad='residentes',
            entidad_id=1,
        )
        AuditLog.objects.create(
            usuario=admin_user,
            accion='crear',
            entidad='medicamentos',
            entidad_id=1,
        )
        response = admin_client.get('/api/audit-log/?entidad=residentes')
        assert response.status_code == 200
        for entry in response.data['results']:
            assert 'residentes' in entry['entidad']

    def test_serializar_instancia(self, admin_user):
        """serializar_instancia convierte modelo a dict correctamente."""
        data = serializar_instancia(admin_user)
        assert isinstance(data, dict)
        assert 'email' in data
        assert data['email'] == 'admin@test.com'

    def test_registrar_auditoria_no_interrumpe(self, api_client, admin_user):
        """El audit log nunca interrumpe la operación principal."""
        from unittest.mock import patch
        # Aunque el audit log falle, la operación sigue
        with patch('auditoria.mixins.AuditLog.objects.create',
                   side_effect=Exception("DB Error")):
            # No debe lanzar excepción
            try:
                from django.test import RequestFactory
                factory = RequestFactory()
                request = factory.get('/')
                request.user = admin_user
                registrar_auditoria(request, 'crear', 'test', 1)
            except Exception:
                pytest.fail("El audit log no debería interrumpir la operación")