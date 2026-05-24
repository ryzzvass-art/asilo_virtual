

import pytest
from django.utils import timezone
from residentes.models import Residente, HistorialMedico
from medicamentos.models import (
    CatalogoMedicamento, ResidenteMedicamento, AdministracionMedicamento
)


# ── Fixtures específicas de medicamentos ──────────────────

@pytest.fixture
def residente(db, admin_user):
    r = Residente.objects.create(
        nombre='Juan', apellido='Pérez',
        dni='12345678',
        fecha_nacimiento='1945-01-01',
        fecha_ingreso='2024-01-01',
        registrado_por=admin_user
    )
    return r


@pytest.fixture
def medicamento_activo(db, admin_user):
    return CatalogoMedicamento.objects.create(
        nombre_comercial='Enalapril 10mg',
        principio_activo='Enalapril maleato',
        tipo='Antihipertensivo',
        forma_farmaceutica='comprimido',
        contraindicaciones='Hipersensibilidad al enalapril',
        creado_por=admin_user
    )


@pytest.fixture
def medicamento_archivado(db, admin_user):
    return CatalogoMedicamento.objects.create(
        nombre_comercial='Med Archivado',
        principio_activo='Principio',
        tipo='Tipo',
        forma_farmaceutica='comprimido',
        estado='archivado',
        creado_por=admin_user
    )


@pytest.fixture
def prescripcion(db, residente, medicamento_activo, admin_user):
    return ResidenteMedicamento.objects.create(
        residente=residente,
        medicamento=medicamento_activo,
        prescrito_por=admin_user,
        dosis='10mg',
        via_administracion='oral',
        horarios=['08:00', '20:00'],
        fecha_inicio='2026-01-01'
    )


# ── Tests de prescripción ──────────────────────────────────

@pytest.mark.django_db
class TestPrescripcion:

    def test_crear_prescripcion_exitosa(self, admin_client, residente, medicamento_activo):
        """Crear prescripción con medicamento activo devuelve 201."""
        response = admin_client.post(
            f'/api/residentes/{residente.pk}/medicamentos/',
            {
                'medicamento': medicamento_activo.pk,
                'dosis': '10mg',
                'via_administracion': 'oral',
                'horarios': ['08:00', '20:00'],
                'fecha_inicio': '2026-01-01'
            },
            format='json'
        )
        assert response.status_code == 201
        assert response.data['estado'] == 'activo'

    def test_prescripcion_medicamento_archivado(
        self, admin_client, residente, medicamento_archivado
    ):
        """Prescribir medicamento archivado devuelve 400."""
        response = admin_client.post(
            f'/api/residentes/{residente.pk}/medicamentos/',
            {
                'medicamento': medicamento_archivado.pk,
                'dosis': '10mg',
                'via_administracion': 'oral',
                'horarios': ['08:00'],
                'fecha_inicio': '2026-01-01'
            },
            format='json'
        )
        assert response.status_code == 400

    def test_finalizar_prescripcion(self, admin_client, residente, prescripcion):
        """Finalizar prescripción activa cambia estado a finalizado."""
        response = admin_client.patch(
            f'/api/residentes/{residente.pk}/medicamentos/{prescripcion.pk}/finalizar/'
        )
        assert response.status_code == 200
        assert response.data['estado'] == 'finalizado'

    def test_listar_solo_activas(self, admin_client, residente, prescripcion):
        """Por defecto solo lista prescripciones activas."""
        response = admin_client.get(
            f'/api/residentes/{residente.pk}/medicamentos/'
        )
        assert response.status_code == 200
        assert len(response.data) == 1


# ── Tests de administración de tomas ──────────────────────

@pytest.mark.django_db
class TestAdministracionTomas:

    def test_registrar_toma_administrada(self, admin_client, prescripcion):
        """Registrar toma administrada devuelve 201."""
        response = admin_client.post('/api/administraciones/', {
            'residente_medicamento': prescripcion.pk,
            'administrado': True,
            'fecha_hora_programada': '2026-01-01T08:00:00',
            'fecha_hora_real': '2026-01-01T08:05:00',
        }, format='json')
        assert response.status_code == 201
        assert response.data['administrado'] is True

    def test_registrar_toma_omitida_sin_observacion(self, admin_client, prescripcion):
        """Toma omitida sin observación devuelve 400."""
        response = admin_client.post('/api/administraciones/', {
            'residente_medicamento': prescripcion.pk,
            'administrado': False,
            'fecha_hora_programada': '2026-01-01T08:00:00',
        }, format='json')
        assert response.status_code == 400

    def test_registrar_toma_omitida_con_observacion(self, admin_client, prescripcion):
        """Toma omitida con observación devuelve 201."""
        response = admin_client.post('/api/administraciones/', {
            'residente_medicamento': prescripcion.pk,
            'administrado': False,
            'fecha_hora_programada': '2026-01-01T08:00:00',
            'observacion': 'Residente no quiso tomar la medicación',
        }, format='json')
        assert response.status_code == 201
        assert response.data['administrado'] is False

    def test_historial_con_resumen(self, admin_client, residente, prescripcion):
        """Historial incluye campo resumen con contadores."""
        # Crear una toma administrada y una omitida
        AdministracionMedicamento.objects.create(
            residente_medicamento=prescripcion,
            realizado_por_id=prescripcion.prescrito_por_id,
            administrado=True,
            fecha_hora_programada=timezone.now()
        )
        AdministracionMedicamento.objects.create(
            residente_medicamento=prescripcion,
            realizado_por_id=prescripcion.prescrito_por_id,
            administrado=False,
            fecha_hora_programada=timezone.now(),
            observacion='No tomó'
        )
        response = admin_client.get(
            f'/api/residentes/{residente.pk}/administraciones/'
        )
        assert response.status_code == 200
        assert 'resumen' in response.data
        assert response.data['resumen']['total_administradas'] == 1
        assert response.data['resumen']['total_omitidas'] == 1