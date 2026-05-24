
import pytest
from residentes.models import Residente
from nutricion.models import (
    CatalogoRestriccion, CatalogoAlimento,
    AlimentoRestriccion, ResidenteRestriccion,
    PlanNutricional
)
from nutricion.views import verificar_restricciones


# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture
def residente(db, admin_user):
    return Residente.objects.create(
        nombre='María', apellido='López',
        dni='87654321',
        fecha_nacimiento='1940-05-10',
        fecha_ingreso='2024-03-01',
        registrado_por=admin_user
    )


@pytest.fixture
def restriccion_obligatoria(db, admin_user):
    return CatalogoRestriccion.objects.create(
        nombre='Sin azúcar',
        descripcion='Para pacientes diabéticos',
        condiciones_asociadas='Diabetes',
        severidad='obligatorio',
        creado_por=admin_user
    )


@pytest.fixture
def restriccion_recomendada(db, admin_user):
    return CatalogoRestriccion.objects.create(
        nombre='Bajo en sodio',
        descripcion='Reducir ingesta de sal',
        condiciones_asociadas='Hipertensión',
        severidad='recomendado',
        creado_por=admin_user
    )


@pytest.fixture
def alimento_sin_restriccion(db):
    a = CatalogoAlimento.objects.create(
        nombre='Arroz blanco',
        grupo_alimentario='cereal',
        estado='activo'
    )
    return a


@pytest.fixture
def alimento_con_restriccion_obligatoria(db, restriccion_obligatoria):
    a = CatalogoAlimento.objects.create(
        nombre='Torta de chocolate',
        grupo_alimentario='postre',
        estado='activo'
    )
    AlimentoRestriccion.objects.create(
        alimento=a, restriccion=restriccion_obligatoria
    )
    return a


@pytest.fixture
def alimento_con_restriccion_recomendada(db, restriccion_recomendada):
    a = CatalogoAlimento.objects.create(
        nombre='Pan blanco',
        grupo_alimentario='cereal',
        estado='activo'
    )
    AlimentoRestriccion.objects.create(
        alimento=a, restriccion=restriccion_recomendada
    )
    return a


@pytest.fixture
def plan_vigente(db, residente, admin_user):
    return PlanNutricional.objects.create(
        residente=residente,
        creado_por=admin_user,
        tipo_dieta='diabetica',
        fecha_inicio='2026-01-01',
        estado='vigente'
    )


# ── Tests de verificar_restricciones() ────────────────────

@pytest.mark.django_db
class TestVerificarRestricciones:

    def test_alimento_sin_conflictos(
        self, residente, alimento_sin_restriccion,
        restriccion_obligatoria, admin_user
    ):
        """Alimento sin restricciones vinculadas no genera conflictos."""
        # Asignar restricción al residente
        ResidenteRestriccion.objects.create(
            residente=residente,
            restriccion=restriccion_obligatoria,
            confirmado_por=admin_user
        )
        conflictos = verificar_restricciones(
            residente.pk, alimento_sin_restriccion.pk
        )
        assert conflictos == []

    def test_alimento_con_restriccion_obligatoria(
        self, residente, alimento_con_restriccion_obligatoria,
        restriccion_obligatoria, admin_user
    ):
        """Alimento que viola restricción obligatoria del residente genera conflicto."""
        ResidenteRestriccion.objects.create(
            residente=residente,
            restriccion=restriccion_obligatoria,
            confirmado_por=admin_user
        )
        conflictos = verificar_restricciones(
            residente.pk, alimento_con_restriccion_obligatoria.pk
        )
        assert len(conflictos) == 1
        assert conflictos[0]['severidad'] == 'obligatorio'

    def test_alimento_con_restriccion_recomendada(
        self, residente, alimento_con_restriccion_recomendada,
        restriccion_recomendada, admin_user
    ):
        """Alimento que viola restricción recomendada genera advertencia."""
        ResidenteRestriccion.objects.create(
            residente=residente,
            restriccion=restriccion_recomendada,
            confirmado_por=admin_user
        )
        conflictos = verificar_restricciones(
            residente.pk, alimento_con_restriccion_recomendada.pk
        )
        assert len(conflictos) == 1
        assert conflictos[0]['severidad'] == 'recomendado'

    def test_residente_sin_restricciones(
        self, residente, alimento_con_restriccion_obligatoria
    ):
        """Residente sin restricciones activas no genera conflictos."""
        conflictos = verificar_restricciones(
            residente.pk, alimento_con_restriccion_obligatoria.pk
        )
        assert conflictos == []


# ── Tests de endpoint de comidas ──────────────────────────

@pytest.mark.django_db
class TestComidaEndpoint:

    def test_comida_bloquea_restriccion_obligatoria(
        self, admin_client, residente,
        alimento_con_restriccion_obligatoria,
        restriccion_obligatoria, plan_vigente, admin_user
    ):
        """POST de comida con restricción obligatoria devuelve 400."""
        ResidenteRestriccion.objects.create(
            residente=residente,
            restriccion=restriccion_obligatoria,
            confirmado_por=admin_user
        )
        response = admin_client.post(
            f'/api/planes/{plan_vigente.pk}/comidas/',
            {
                'fecha': '2026-05-05',
                'tipo_comida': 'almuerzo',
                'alimento': alimento_con_restriccion_obligatoria.pk,
            },
            format='json'
        )
        assert response.status_code == 400
        assert 'conflictos' in response.data

    def test_comida_guarda_con_advertencia_recomendada(
        self, admin_client, residente,
        alimento_con_restriccion_recomendada,
        restriccion_recomendada, plan_vigente, admin_user
    ):
        """POST de comida con restricción recomendada devuelve 201 con advertencias."""
        ResidenteRestriccion.objects.create(
            residente=residente,
            restriccion=restriccion_recomendada,
            confirmado_por=admin_user
        )
        response = admin_client.post(
            f'/api/planes/{plan_vigente.pk}/comidas/',
            {
                'fecha': '2026-05-05',
                'tipo_comida': 'merienda',
                'alimento': alimento_con_restriccion_recomendada.pk,
            },
            format='json'
        )
        assert response.status_code == 201
        assert 'advertencias' in response.data

    def test_comida_sin_conflicto(
        self, admin_client, alimento_sin_restriccion, plan_vigente
    ):
        """POST de comida sin conflictos devuelve 201 limpio."""
        response = admin_client.post(
            f'/api/planes/{plan_vigente.pk}/comidas/',
            {
                'fecha': '2026-05-05',
                'tipo_comida': 'desayuno',
                'alimento': alimento_sin_restriccion.pk,
            },
            format='json'
        )
        assert response.status_code == 201
        assert 'advertencias' not in response.data
        assert 'conflictos' not in response.data