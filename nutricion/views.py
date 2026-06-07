from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
import datetime

from auditoria.mixins import (
    AuditLogMixin,
    serializar_instancia,
    registrar_auditoria,
)

from .models import (
    CatalogoRestriccion,
    CatalogoAlimento,
    AlimentoRestriccion,
    ResidenteRestriccion,
    PlanNutricional,
    ComidaDiaria,
    PlantillaNutricional,
    ComidaPlantilla,
)
from .serializers import (
    CatalogoRestriccionSerializer,
    CatalogoAlimentoSerializer,
    AlimentoRestriccionSerializer,
    ResidenteRestriccionSerializer,
    AsignarRestriccionSerializer,
    PlanNutricionalSerializer,
    ComidaDiariaSerializer,
    PlantillaNutricionalSerializer,     # nuevo
    RechazarPlantillaSerializer,        # nuevo
    AsignarPlantillaSerializer,
)
from usuarios.permissions import IsAdministrador, IsAdminOrCuidador
from residentes.models import Residente
from django.db import transaction

# ── T-59, T-60 — Catalogo de Restricciones ────────────────


class RestriccionListCreateView(AuditLogMixin, APIView):
    """
    GET  /api/restricciones/  → listar activas (todos los roles)
    POST /api/restricciones/  → crear (solo Admin)
    """

    audit_entidad = "restricciones"

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdministrador()]
        return [IsAdminOrCuidador()]

    def get(self, request):
        incluir = request.query_params.get("incluir_archivadas", "false")
        if incluir.lower() == "true":
            queryset = CatalogoRestriccion.objects.all()
        else:
            queryset = CatalogoRestriccion.objects.filter(estado="activo")
        serializer = CatalogoRestriccionSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = CatalogoRestriccionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        instancia = serializer.save(creado_por=request.user)

        # AUDITORÍA: registrar creación de restricción
        self.audit_crear(request, instancia)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class RestriccionDetailView(AuditLogMixin, APIView):
    """
    GET   /api/restricciones/{id}/  → detalle
    PATCH /api/restricciones/{id}/  → editar (solo Admin)
    """

    audit_entidad = "restricciones"

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [IsAdministrador()]
        return [IsAdminOrCuidador()]

    def get(self, request, pk):
        restriccion = get_object_or_404(CatalogoRestriccion, pk=pk)
        return Response(CatalogoRestriccionSerializer(restriccion).data)

    def patch(self, request, pk):
        restriccion = get_object_or_404(CatalogoRestriccion, pk=pk)

        # AUDITORÍA: snapshot ANTES de editar
        antes = serializar_instancia(restriccion)

        serializer = CatalogoRestriccionSerializer(
            restriccion, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()

        # AUDITORÍA: registrar edición con snapshot antes/después
        restriccion.refresh_from_db()
        self.audit_editar(request, antes, restriccion)

        return Response(serializer.data)


class RestriccionArchivarView(AuditLogMixin, APIView):
    """PATCH /api/restricciones/{id}/archivar/ → archivar (solo Admin)"""

    audit_entidad = "restricciones"
    permission_classes = [IsAdministrador]

    def patch(self, request, pk):
        restriccion = get_object_or_404(CatalogoRestriccion, pk=pk)
        if restriccion.estado == "archivado":
            return Response(
                {"error": "Esta restricción ya está archivada."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        antes = serializar_instancia(restriccion)

        restriccion.estado = "archivado"
        restriccion.save(update_fields=["estado"])

        # AUDITORÍA: registrar archivado
        self.audit_editar(request, antes, restriccion)

        return Response(
            {
                "mensaje": f"Restricción '{restriccion.nombre}' archivada.",
                "estado": restriccion.estado,
            }
        )


# ── T-61, T-62 — Catalogo de Alimentos ────────────────────


class AlimentoListCreateView(AuditLogMixin, APIView):
    """
    GET  /api/alimentos/  → listar activos (todos los roles)
    POST /api/alimentos/  → crear con estado='pendiente'
    """

    audit_entidad = "alimentos"

    def get_permissions(self):

        return [IsAdminOrCuidador()]

    def get(self, request):
        incluir = request.query_params.get("incluir_no_activos", "false")
        if incluir.lower() == "true":
            queryset = CatalogoAlimento.objects.all()
        else:
            queryset = CatalogoAlimento.objects.filter(estado="activo")

        nombre = request.query_params.get("nombre")
        if nombre:
            queryset = queryset.filter(nombre__icontains=nombre)

        serializer = CatalogoAlimentoSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        """T-62: Nuevo alimento siempre inicia con estado='pendiente'."""
        serializer = CatalogoAlimentoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        # estado='pendiente' es el default del modelo, no se puede forzar activo
        instancia = serializer.save()

        # AUDITORÍA: registrar creación de alimento (estado pendiente)
        self.audit_crear(request, instancia)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AlimentoActivarView(AuditLogMixin, APIView):
    """
    PATCH /api/alimentos/{id}/activar/
    T-62: Solo Admin puede activar. Registra revisado_por.
    """

    audit_entidad = "alimentos"
    permission_classes = [IsAdministrador]

    def patch(self, request, pk):
        alimento = get_object_or_404(CatalogoAlimento, pk=pk)
        if alimento.estado == "activo":
            return Response(
                {"error": "Este alimento ya está activo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        antes = serializar_instancia(alimento)

        alimento.estado = "activo"
        alimento.revisado_por = request.user
        alimento.save(update_fields=["estado", "revisado_por"])

        # AUDITORÍA: registrar activación
        self.audit_editar(request, antes, alimento)

        return Response(
            {
                "mensaje": f"Alimento '{alimento.nombre}' activado.",
                "estado": alimento.estado,
                "revisado_por": f"{request.user.nombre} {request.user.apellido}",
            }
        )

class AlimentoArchivarView(AuditLogMixin, APIView):
    """
    PATCH /api/alimentos/{id}/archivar/  → solo Admin
    """
    audit_entidad = "alimentos"
    permission_classes = [IsAdministrador]

    def patch(self, request, pk):
        alimento = get_object_or_404(CatalogoAlimento, pk=pk)
        if alimento.estado == 'archivado':
            return Response(
                {'error': 'Este alimento ya está archivado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        antes = serializar_instancia(alimento)

        alimento.estado = 'archivado'
        alimento.save(update_fields=['estado'])

        # AUDITORÍA: registrar archivado
        self.audit_editar(request, antes, alimento)

        return Response({'mensaje': f"Alimento '{alimento.nombre}' archivado."})

class AlimentoDetailView(AuditLogMixin, APIView):
    """
    GET   /api/alimentos/{id}/  → detalle con restricciones que viola
    PATCH /api/alimentos/{id}/  → editar (solo Admin)
    """

    audit_entidad = "alimentos"

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [IsAdministrador()]
        return [IsAdminOrCuidador()]

    def get(self, request, pk):
        alimento = get_object_or_404(CatalogoAlimento, pk=pk)
        serializer = CatalogoAlimentoSerializer(alimento)
        return Response(serializer.data)

    def patch(self, request, pk):
        alimento = get_object_or_404(CatalogoAlimento, pk=pk)

        # AUDITORÍA: snapshot ANTES de editar
        antes = serializar_instancia(alimento)

        serializer = CatalogoAlimentoSerializer(
            alimento, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()

        # AUDITORÍA: registrar edición con snapshot antes/después
        alimento.refresh_from_db()
        self.audit_editar(request, antes, alimento)

        return Response(serializer.data)


# ── T-63, T-64 — Vinculacion Alimento-Restriccion ─────────


class AlimentoRestriccionView(AuditLogMixin, APIView):
    """
    GET    /api/alimentos/{id}/restricciones/              → listar restricciones del alimento
    POST   /api/alimentos/{id}/restricciones/              → vincular restricción
    DELETE /api/alimentos/{id}/restricciones/{rid}/        → desvincular
    """

    audit_entidad = "alimento_restricciones"
    permission_classes = [IsAdministrador]

    def get(self, request, pk):
        alimento = get_object_or_404(CatalogoAlimento, pk=pk)
        vínculos = AlimentoRestriccion.objects.filter(alimento=alimento).select_related(
            "restriccion"
        )
        serializer = AlimentoRestriccionSerializer(vínculos, many=True)
        return Response(serializer.data)

    def post(self, request, pk):
        """T-64: Vincular restricción a alimento."""
        alimento = get_object_or_404(CatalogoAlimento, pk=pk)

        restriccion_id = request.data.get("restriccion_id")
        if not restriccion_id:
            return Response(
                {"error": "restriccion_id es requerido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        restriccion = get_object_or_404(CatalogoRestriccion, pk=restriccion_id)

        # Verificar que no exista ya el vinculo
        if AlimentoRestriccion.objects.filter(
            alimento=alimento, restriccion=restriccion
        ).exists():
            return Response(
                {"error": "Esta restricción ya está vinculada a este alimento."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        vinculo = AlimentoRestriccion.objects.create(
            alimento=alimento, restriccion=restriccion
        )

        # AUDITORÍA: registrar creación del vínculo
        self.audit_crear(request, vinculo)

        serializer = AlimentoRestriccionSerializer(vinculo)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request, pk, rid):
        alimento = get_object_or_404(CatalogoAlimento, pk=pk)
        restriccion = get_object_or_404(CatalogoRestriccion, pk=rid)
        vinculo = get_object_or_404(
            AlimentoRestriccion, alimento=alimento, restriccion=restriccion
        )

        # AUDITORÍA: snapshot ANTES de borrar (es un borrado real)
        antes = serializar_instancia(vinculo)
        vinculo_id = vinculo.pk

        vinculo.delete()

        # AUDITORÍA: registrar eliminación del vínculo
        registrar_auditoria(
            request=request,
            accion="eliminar",
            entidad_nombre=self.audit_entidad,
            entidad_id=vinculo_id,
            datos_anteriores=antes,
            datos_nuevos=None,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


# ── T-65, T-66, T-67 — Restricciones del Residente ────────


class ResidenteRestriccionView(AuditLogMixin, APIView):

    audit_entidad = "residente_restricciones"
    permission_classes = [IsAdminOrCuidador]

    def get(self, request, pk):
        residente = get_object_or_404(Residente, pk=pk)
        queryset = ResidenteRestriccion.objects.filter(
            residente=residente, estado="activa"
        ).select_related("restriccion", "confirmado_por")
        serializer = ResidenteRestriccionSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request, pk):
        residente = get_object_or_404(Residente, pk=pk)
        serializer = AsignarRestriccionSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        restriccion = serializer.validated_data["restriccion"]

        # Verificar si ya existe (activa o revocada)
        existente = ResidenteRestriccion.objects.filter(
            residente=residente,
            restriccion=restriccion,
        ).first()

        if existente:
            if existente.estado == "activa":
                return Response(
                    {
                        "error": f"La restricción '{restriccion.nombre}' ya está activa para este residente."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Si está revocada → reactivar en lugar de crear nueva
            antes = serializar_instancia(existente)
            existente.estado = "activa"
            existente.confirmado_por = request.user
            existente.save(update_fields=["estado", "confirmado_por"])
            rr = existente

            # AUDITORÍA: reactivación de restricción revocada (edición)
            self.audit_editar(request, antes, rr)
        else:
            # Crear nueva
            rr = ResidenteRestriccion.objects.create(
                residente=residente,
                restriccion=restriccion,
                confirmado_por=request.user,
            )

            # AUDITORÍA: creación de nueva restricción del residente
            self.audit_crear(request, rr)

        # Sugerencias basadas en condiciones_cronicas
        sugeridas = []
        try:
            condiciones = residente.historial_medico.condiciones_cronicas.lower()
            if condiciones:
                otras = CatalogoRestriccion.objects.filter(estado="activo").exclude(
                    pk=restriccion.pk
                )
                for r in otras:
                    palabras = [
                        p.strip()
                        for p in r.condiciones_asociadas.lower().split(",")
                        if len(p.strip()) > 3
                    ]
                    if any(p in condiciones for p in palabras):
                        ya_activa = ResidenteRestriccion.objects.filter(
                            residente=residente, restriccion=r, estado="activa"
                        ).exists()
                        if not ya_activa:
                            sugeridas.append(
                                {
                                    "id": r.pk,
                                    "nombre": r.nombre,
                                    "severidad": r.severidad,
                                }
                            )
        except Exception:
            pass

        response_data = ResidenteRestriccionSerializer(rr).data
        if sugeridas:
            response_data = dict(response_data)
            response_data["sugeridas"] = sugeridas

        return Response(response_data, status=status.HTTP_201_CREATED)


class ResidenteRestriccionRevocarView(AuditLogMixin, APIView):
    """PATCH /api/residentes/{id}/restricciones/{rr_id}/revocar/"""

    audit_entidad = "residente_restricciones"
    permission_classes = [IsAdminOrCuidador]

    def patch(self, request, pk, rr_id):
        residente = get_object_or_404(Residente, pk=pk)
        rr = get_object_or_404(ResidenteRestriccion, pk=rr_id, residente=residente)
        if rr.estado == "revocada":
            return Response(
                {"error": "Esta restricción ya está revocada."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        antes = serializar_instancia(rr)

        rr.estado = "revocada"
        rr.save(update_fields=["estado"])

        # AUDITORÍA: registrar revocación
        self.audit_editar(request, antes, rr)

        return Response(
            {
                "mensaje": f"Restricción '{rr.restriccion.nombre}' revocada.",
                "estado": rr.estado,
            }
        )

class RestriccionActivarView(AuditLogMixin, APIView):

    audit_entidad = "restricciones"
    permission_classes = [IsAdministrador]

    def patch(self, request, pk):
        restriccion = get_object_or_404(CatalogoRestriccion, pk=pk)
        if restriccion.estado == 'activo':
            return Response(
                {'error': 'Esta restricción ya está activa.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        antes = serializar_instancia(restriccion)

        restriccion.estado = 'activo'
        restriccion.save(update_fields=['estado'])

        # AUDITORÍA: registrar activación
        self.audit_editar(request, antes, restriccion)

        return Response({'mensaje': f"Restricción '{restriccion.nombre}' activada."})

    ## ── Funcion de servicio RF-25 — T-73 ──────────────────────


def verificar_restricciones(residente_id, alimento_id):
    """
    T-73: Verifica si un alimento viola restricciones activas del residente.

    Retorna lista vacía si no hay conflictos.
    Retorna lista con {restriccion, severidad} si hay conflictos.

    Esta función se reutiliza en el endpoint de comidas (T-74).
    """
    from .models import AlimentoRestriccion, ResidenteRestriccion, CatalogoAlimento

    # Restricciones activas del residente
    restricciones_activas = ResidenteRestriccion.objects.filter(
        residente_id=residente_id, estado="activa"
    ).values_list("restriccion_id", flat=True)

    if not restricciones_activas:
        return []

    # Restricciones que viola el alimento
    conflictos = AlimentoRestriccion.objects.filter(
        alimento_id=alimento_id, restriccion_id__in=restricciones_activas
    ).select_related("restriccion")

    return [
        {
            "restriccion_id": c.restriccion.pk,
            "restriccion": c.restriccion.nombre,
            "severidad": c.restriccion.severidad,
        }
        for c in conflictos
    ]


# ── T-68, T-69 — Planes Nutricionales ─────────────────────


class PlanListView(APIView):
    """
    GET /api/residentes/{id}/planes/  → listar todos los planes del residente (T-75)
    La creación de planes ahora se hace exclusivamente vía AsignarPlantillaView
    (POST /residentes/{id}/planes/asignar/).
    """

    permission_classes = [IsAdminOrCuidador]

    def get(self, request, pk):
        """T-75: Lista vigente + archivados ordenados por fecha_inicio DESC."""
        residente = get_object_or_404(Residente, pk=pk)
        planes = PlanNutricional.objects.filter(residente=residente).select_related(
            "creado_por", "plantilla_origen"
        )
        serializer = PlanNutricionalSerializer(planes, many=True)
        return Response(serializer.data)


class PlanDetailView(APIView):
    """
    GET /api/planes/{id}/  → detalle del plan con sus comidas (T-76)
    """

    permission_classes = [IsAdminOrCuidador]

    def get(self, request, plan_id):
        """T-76: Plan específico con sus comidas — accesible aunque este archivado."""
        plan = get_object_or_404(PlanNutricional, pk=plan_id)
        serializer = PlanNutricionalSerializer(plan)
        data = dict(serializer.data)

        # Incluir comidas del plan
        comidas = ComidaDiaria.objects.filter(plan=plan).select_related(
            "alimento", "registrado_por"
        )
        data["comidas"] = ComidaDiariaSerializer(comidas, many=True).data

        return Response(data)


# ── T-70, T-71, T-72, T-73, T-74 — Comidas Diarias ────────


class ComidaListCreateView(AuditLogMixin, APIView):
    """
    GET  /api/planes/{id}/comidas/  → listar comidas del plan (T-72)
    POST /api/planes/{id}/comidas/  → registrar comida con verificación RF-25 (T-74)
    """

    audit_entidad = "comidas_diarias"
    permission_classes = [IsAdminOrCuidador]

    def get(self, request, plan_id):
        """T-72: Lista con filtros opcionales ?fecha= y ?tipo_comida="""
        plan = get_object_or_404(PlanNutricional, pk=plan_id)
        queryset = ComidaDiaria.objects.filter(plan=plan).select_related(
            "alimento", "registrado_por"
        )

        # Filtros opcionales
        fecha = request.query_params.get("fecha")
        tipo_comida = request.query_params.get("tipo_comida")

        if fecha:
            queryset = queryset.filter(fecha=fecha)
        if tipo_comida:
            tipos_validos = [t[0] for t in ComidaDiaria.TipoComida.choices]
            if tipo_comida not in tipos_validos:
                return Response(
                    {"error": f"tipo_comida inválido. Opciones: {tipos_validos}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            queryset = queryset.filter(tipo_comida=tipo_comida)

        serializer = ComidaDiariaSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request, plan_id):
        """
        T-74: Registrar comida con verificacion automática de restricciones.
        - Conflicto 'obligatorio' → bloquea con 400
        - Conflicto 'recomendado' → guarda con campo 'advertencias'
        - Sin conflicto → guarda normalmente
        """
        plan = get_object_or_404(PlanNutricional, pk=plan_id)

        # Solo se pueden agregar comidas al plan vigente
        if plan.estado == "archivado":
            return Response(
                {"error": "No se pueden agregar comidas a un plan archivado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ComidaDiariaSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        alimento = serializer.validated_data["alimento"]
        residente_id = plan.residente_id

        # T-73, T-74: Verificar restricciones
        conflictos = verificar_restricciones(residente_id, alimento.pk)

        # Separar por severidad
        obligatorios = [c for c in conflictos if c["severidad"] == "obligatorio"]
        recomendados = [c for c in conflictos if c["severidad"] == "recomendado"]

        # Conflicto obligatorio → bloquear
        if obligatorios:
            nombres_restricciones = ", ".join(c["restriccion"] for c in obligatorios)
            return Response(
                {
                    "error": (
                        f"No se puede agregar '{alimento.nombre}': viola "
                        f"{'la restricción obligatoria' if len(obligatorios) == 1 else 'las restricciones obligatorias'} "
                        f"{nombres_restricciones} del residente."
                    ),
                    "conflictos": obligatorios,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Guardar la comida
        comida = serializer.save(plan=plan, registrado_por=request.user)

        # AUDITORÍA: registrar creación de comida diaria
        self.audit_crear(request, comida)

        response_data = ComidaDiariaSerializer(comida).data

        # Conflicto recomendado → guardar con advertencias
        if recomendados:
            response_data = dict(response_data)
            response_data["advertencias"] = recomendados

        return Response(response_data, status=status.HTTP_201_CREATED)

class ComidaDetailView(AuditLogMixin, APIView):
    """DELETE /api/comidas/{id}/ → quitar una comida del menú"""

    audit_entidad = "comidas_diarias"
    permission_classes = [IsAdminOrCuidador]

    def delete(self, request, comida_id):
        comida = get_object_or_404(ComidaDiaria, pk=comida_id)

        # AUDITORÍA: snapshot ANTES de borrar (es un borrado real)
        antes = serializar_instancia(comida)
        comida_pk = comida.pk

        comida.delete()

        # AUDITORÍA: registrar eliminación de comida
        registrar_auditoria(
            request=request,
            accion="eliminar",
            entidad_nombre=self.audit_entidad,
            entidad_id=comida_pk,
            datos_anteriores=antes,
            datos_nuevos=None,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)

# ── Fase 2: Plantillas Nutricionales ──────────────────────


class PlantillaListCreateView(AuditLogMixin, APIView):
    """
    GET  /api/plantillas/  → listar (filtro ?estado=pendiente|aprobado|rechazado)
    POST /api/plantillas/  → crear plantilla con comidas (Admin o Cuidador)
    """

    audit_entidad = "plantillas_nutricionales"
    permission_classes = [IsAdminOrCuidador]

    def get(self, request):
        estado = request.query_params.get("estado")
        fecha  = request.query_params.get("fecha")

        queryset = PlantillaNutricional.objects.select_related(
            "creado_por", "aprobado_por"
        ).prefetch_related("comidas__alimento")

        if estado:
            queryset = queryset.filter(estado=estado)

        # Aprobadas: por defecto solo fecha >= hoy, salvo que se pase ?fecha=
        if estado == "aprobado":
            if fecha:
                queryset = queryset.filter(fecha_menu=fecha)
            else:
                hoy = timezone.now().date()
                queryset = queryset.filter(fecha_menu__gte=hoy)

        # Rechazadas: si llega ?fecha= filtra por esa fecha; si no, últimas 2 semanas
        if estado == "rechazado":
            if fecha:
                queryset = queryset.filter(fecha_menu=fecha)
            else:
                hace_dos_semanas = timezone.now().date() - datetime.timedelta(days=14)
                queryset = queryset.filter(fecha_menu__gte=hace_dos_semanas)

        serializer = PlantillaNutricionalSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = PlantillaNutricionalSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        instancia = serializer.save(creado_por=request.user)

        # AUDITORÍA: registrar creación de plantilla
        self.audit_crear(request, instancia)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

class PlantillaDetailView(APIView):
    """
    GET /api/plantillas/{id}/  → detalle con comidas
    """

    permission_classes = [IsAdminOrCuidador]

    def get(self, request, pk):
        plantilla = get_object_or_404(
            PlantillaNutricional.objects.prefetch_related("comidas__alimento"),
            pk=pk,
        )
        return Response(PlantillaNutricionalSerializer(plantilla).data)

class PlantillaEditarView(AuditLogMixin, APIView):
    """
    PATCH /api/plantillas/{id}/editar/
    Solo disponible mientras la plantilla está en estado pendiente.
    Cualquier usuario autenticado (Admin o Cuidador) puede editar la suya.
    """
    audit_entidad = "plantillas_nutricionales"
    permission_classes = [IsAdminOrCuidador]

    def patch(self, request, pk):
        plantilla = get_object_or_404(PlantillaNutricional, pk=pk)

        if plantilla.estado != 'pendiente':
            return Response(
                {'error': 'Solo se pueden editar plantillas en estado pendiente.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if plantilla.creado_por_id != request.user.id:
            return Response(
                {'error': 'Solo puedes editar los planes que tú creaste.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # AUDITORÍA: snapshot ANTES de editar
        antes = serializar_instancia(plantilla)

        # Eliminar comidas anteriores y reemplazar con las nuevas
        serializer = PlantillaNutricionalSerializer(
            plantilla, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Si vienen comidas nuevas, validar las 4 antes de reemplazar (BUG 2)
        comidas_data = request.data.get('comidas')
        if comidas_data is not None:
            TIPOS_REQUERIDOS = {"desayuno", "almuerzo", "merienda", "cena"}
            tipos = {c.get('tipo_comida') for c in comidas_data}
            if tipos != TIPOS_REQUERIDOS:
                return Response(
                    {"error": "El plan debe incluir desayuno, almuerzo, merienda y cena."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            for comida in comidas_data:
                try:
                    al = CatalogoAlimento.objects.get(pk=comida['alimento'])
                except CatalogoAlimento.DoesNotExist:
                    return Response(
                        {"error": f"Alimento {comida['alimento']} no existe."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if al.estado != 'activo':
                    return Response(
                        {"error": f"El alimento '{al.nombre}' no está activo."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            plantilla.comidas.all().delete()
            for comida in comidas_data:
                ComidaPlantilla.objects.create(plantilla=plantilla, **{
                    'tipo_comida': comida['tipo_comida'],
                    'alimento_id': comida['alimento'],
                    'descripcion_menu': comida.get('descripcion_menu', ''),
                })

        # Guardar campos del form sin tocar comidas (usar valores ya validados)
        for field in ['nombre', 'tipo_dieta', 'observaciones', 'fecha_menu']:
            if field in serializer.validated_data:
                setattr(plantilla, field, serializer.validated_data[field])
        plantilla.save()

        # AUDITORÍA: registrar edición con snapshot antes/después
        plantilla.refresh_from_db()
        self.audit_editar(request, antes, plantilla)

        return Response(
            PlantillaNutricionalSerializer(plantilla).data
        )


class PlantillaAprobarView(AuditLogMixin, APIView):
    """
    PATCH /api/plantillas/{id}/aprobar/  → solo Admin
    """

    audit_entidad = "plantillas_nutricionales"
    permission_classes = [IsAdministrador]

    def patch(self, request, pk):
        plantilla = get_object_or_404(PlantillaNutricional, pk=pk)

        if plantilla.estado == "aprobado":
            return Response(
                {"error": "Esta plantilla ya está aprobada."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if plantilla.estado == "rechazado":
            return Response(
                {"error": "No se puede aprobar una plantilla rechazada. Debe reformularse."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        antes = serializar_instancia(plantilla)

        plantilla.estado = "aprobado"
        plantilla.aprobado_por = request.user
        plantilla.motivo_rechazo = ""
        plantilla.save(update_fields=["estado", "aprobado_por", "motivo_rechazo"])

        # AUDITORÍA: registrar aprobación
        self.audit_editar(request, antes, plantilla)

        return Response(
            {
                "mensaje": f"Plantilla '{plantilla.nombre}' aprobada.",
                "estado": plantilla.estado,
                "aprobado_por": f"{request.user.nombre} {request.user.apellido}",
            }
        )


class PlantillaRechazarView(AuditLogMixin, APIView):
    """
    PATCH /api/plantillas/{id}/rechazar/  → solo Admin, requiere motivo_rechazo
    """

    audit_entidad = "plantillas_nutricionales"
    permission_classes = [IsAdministrador]

    def patch(self, request, pk):
        plantilla = get_object_or_404(PlantillaNutricional, pk=pk)

        if plantilla.estado == "rechazado":
            return Response(
                {"error": "Esta plantilla ya está rechazada."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if plantilla.estado == "aprobado":
            return Response(
                {"error": "No se puede rechazar una plantilla ya aprobada."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = RechazarPlantillaSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        antes = serializar_instancia(plantilla)

        plantilla.estado = "rechazado"
        plantilla.aprobado_por = request.user
        plantilla.motivo_rechazo = serializer.validated_data["motivo_rechazo"]
        plantilla.save(update_fields=["estado", "aprobado_por", "motivo_rechazo"])

        # AUDITORÍA: registrar rechazo
        self.audit_editar(request, antes, plantilla)

        return Response(
            {
                "mensaje": f"Plantilla '{plantilla.nombre}' rechazada.",
                "estado": plantilla.estado,
                "motivo_rechazo": plantilla.motivo_rechazo,
            }
        )


class AsignarPlantillaView(AuditLogMixin, APIView):
    """
    POST /api/residentes/{id}/planes/asignar/

    Paso 1 — sin reemplazos:
        body: { plantilla_id, fecha_inicio }
        → Si hay conflictos: 200 con { conflictos, sugerencias } (no guarda)
        → Si no hay conflictos: 201, plan creado y vigente

    Paso 2 — con reemplazos resueltos:
        body: { plantilla_id, fecha_inicio, reemplazos: [{comida_plantilla_id, alimento_id}] }
        → Si quedan conflictos sin resolver: 400
        → Si todo ok: 201, plan creado y vigente
    """

    audit_entidad = "planes_nutricionales"
    permission_classes = [IsAdminOrCuidador]

    def post(self, request, pk):
        residente = get_object_or_404(Residente, pk=pk)
        serializer = AsignarPlantillaSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        plantilla_id = serializer.validated_data["plantilla_id"]
        fecha_inicio = serializer.validated_data["fecha_inicio"]
        reemplazos   = serializer.validated_data["reemplazos"]

        plantilla = get_object_or_404(PlantillaNutricional, pk=plantilla_id)

        # Construir mapa de reemplazos: {comida_plantilla_id: alimento_id}
        mapa_reemplazos = {}
        for r in reemplazos:
            try:
                cid = int(r["comida_plantilla_id"])
                aid = int(r["alimento_id"])
                mapa_reemplazos[cid] = aid
            except (KeyError, ValueError, TypeError):
                return Response(
                    {"error": "Formato de reemplazos inválido. Usa [{comida_plantilla_id, alimento_id}]."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Verificar que los alimentos de reemplazo existen y están activos
        if mapa_reemplazos:
            alimentos_reemplazo = CatalogoAlimento.objects.filter(
                pk__in=mapa_reemplazos.values(), estado="activo"
            )
            ids_validos = set(a.pk for a in alimentos_reemplazo)
            for aid in mapa_reemplazos.values():
                if aid not in ids_validos:
                    return Response(
                        {"error": f"El alimento de reemplazo con id {aid} no existe o no está activo."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        comidas_plantilla = plantilla.comidas.select_related("alimento").all()

        # ── Verificar conflictos para cada comida ─────────
        conflictos_pendientes = []      # comidas que aún tienen conflicto
        plan_comidas = []               # lista final de comidas a guardar
        advertencias_recomendadas = []  # OBS 5: recomendados no bloqueantes

        for comida in comidas_plantilla:
            # Si hay reemplazo para esta comida, usarlo
            alimento_final_id = mapa_reemplazos.get(comida.pk, comida.alimento_id)

            conflictos = verificar_restricciones(residente.pk, alimento_final_id)
            obligatorios = [c for c in conflictos if c["severidad"] == "obligatorio"]
            recomendados = [c for c in conflictos if c["severidad"] == "recomendado"]

            # OBS 5: registrar advertencias recomendadas (no bloquean la asignación)
            for rec in recomendados:
                advertencias_recomendadas.append({
                    "tipo_comida": comida.tipo_comida,
                    "alimento_id": alimento_final_id,
                    "restriccion": rec["restriccion"],
                })

            if obligatorios:
                # Buscar sugerencias: alimentos activos del mismo grupo que no tengan conflicto
                sugerencias = _sugerir_reemplazos(
                    residente.pk,
                    comida.alimento.grupo_alimentario,
                    excluir_id=alimento_final_id,
                )
                conflictos_pendientes.append({
                    "comida_plantilla_id": comida.pk,
                    "tipo_comida": comida.tipo_comida,
                    "alimento_id": alimento_final_id,
                    "alimento_nombre": comida.alimento.nombre
                        if alimento_final_id == comida.alimento_id
                        else CatalogoAlimento.objects.get(pk=alimento_final_id).nombre,
                    "conflictos": obligatorios,
                    "sugerencias": sugerencias,
                })
            else:
                plan_comidas.append({
                    "alimento_id": alimento_final_id,
                    "tipo_comida": comida.tipo_comida,
                    "descripcion_menu": comida.descripcion_menu,
                })

        # Si quedan conflictos sin resolver → devolver sin guardar (Paso 1 o Paso 2 incompleto)
        if conflictos_pendientes:
            return Response(
                {
                    "mensaje": "Hay conflictos con las restricciones del residente. "
                               "Resuelve los reemplazos y vuelve a enviar.",
                    "conflictos": conflictos_pendientes,
                },
                status=status.HTTP_200_OK,   # 200 porque no es un error, es información
            )

        # ── Sin conflictos → guardar ───────────────────────
        with transaction.atomic():
            # Archivar plan vigente anterior
            PlanNutricional.objects.filter(
                residente=residente, estado="vigente"
            ).update(estado="archivado", fecha_fin=fecha_inicio)

            # Crear el nuevo plan
            plan = PlanNutricional.objects.create(
                residente=residente,
                creado_por=request.user,
                plantilla_origen=plantilla,
                tipo_dieta=plantilla.tipo_dieta,
                observaciones=plantilla.observaciones,
                fecha_inicio=fecha_inicio,
                estado="vigente",
            )

            # Copiar comidas al plan del residente
            for c in plan_comidas:
                ComidaDiaria.objects.create(
                    plan=plan,
                    registrado_por=request.user,
                    fecha=fecha_inicio,
                    tipo_comida=c["tipo_comida"],
                    alimento_id=c["alimento_id"],
                    descripcion_menu=c["descripcion_menu"],
                )

        # AUDITORÍA: registrar creación del plan (la transacción ya hizo commit).
        # Solo se llega aquí cuando el plan se guardó (no en el paso 1 con conflictos).
        self.audit_crear(request, plan)

        response_data = dict(PlanNutricionalSerializer(plan).data)
        if advertencias_recomendadas:
            response_data["advertencias"] = advertencias_recomendadas
        return Response(response_data, status=status.HTTP_201_CREATED)


def _sugerir_reemplazos(residente_id, grupo_alimentario, excluir_id, limite=5):
    """
    Devuelve hasta `limite` alimentos activos del mismo grupo
    que no tengan conflicto obligatorio con el residente.
    """
    candidatos = CatalogoAlimento.objects.filter(
        estado="activo",
        grupo_alimentario=grupo_alimentario,
    ).exclude(pk=excluir_id)

    sugerencias = []
    for alimento in candidatos:
        conflictos = verificar_restricciones(residente_id, alimento.pk)
        obligatorios = [c for c in conflictos if c["severidad"] == "obligatorio"]
        if not obligatorios:
            sugerencias.append({
                "alimento_id": alimento.pk,
                "nombre": alimento.nombre,
                "grupo_alimentario": alimento.grupo_alimentario,
            })
        if len(sugerencias) >= limite:
            break

    return sugerencias


# ── Resumen de Nutrición para el Dashboard ────────────────


class NutricionResumenView(APIView):
    """
    GET /api/nutricion/resumen-dashboard/
    Métricas + listas de nutrición para el dashboard.
    """

    permission_classes = [IsAdminOrCuidador]

    def get(self, request):
        hoy = timezone.now().date()

        residentes_activos = Residente.objects.filter(estado="activo")
        total_activos = residentes_activos.count()

        ids_con_plan = PlanNutricional.objects.filter(
            estado="vigente"
        ).values_list("residente_id", flat=True)

        sin_plan = residentes_activos.exclude(pk__in=ids_con_plan)
        sin_plan_lista = [
            {"id": r.pk, "nombre": f"{r.nombre} {r.apellido}"}
            for r in sin_plan
        ]
        con_plan_count = total_activos - len(sin_plan_lista)

        # Planes pendientes (plantillas) + lista
        pendientes_qs = PlantillaNutricional.objects.filter(
            estado="pendiente"
        ).select_related("creado_por").order_by("-created_at")
        pendientes_lista = [
            {"id": p.id, "nombre": p.nombre, "tipo": p.tipo_dieta,
             "creado_por": f"{p.creado_por.nombre} {p.creado_por.apellido}"}
            for p in pendientes_qs
        ]

        # Planes aprobados vigentes (fecha_menu >= hoy) + lista
        aprobados_qs = PlantillaNutricional.objects.filter(
            estado="aprobado", fecha_menu__gte=hoy
        ).order_by("fecha_menu")
        aprobados_lista = [
            {"id": p.id, "nombre": p.nombre, "tipo": p.tipo_dieta, "fecha": str(p.fecha_menu)}
            for p in aprobados_qs
        ]

        # Alimentos activos + lista
        alimentos_qs = CatalogoAlimento.objects.filter(
            estado="activo"
        ).order_by("nombre")
        alimentos_lista = [
            {"id": a.id, "nombre": a.nombre, "grupo": a.grupo_alimentario}
            for a in alimentos_qs
        ]

        # Restricciones activas + lista
        restricciones_qs = CatalogoRestriccion.objects.filter(
            estado="activo"
        ).order_by("nombre")
        restricciones_lista = [
            {"id": r.id, "nombre": r.nombre, "severidad": r.severidad}
            for r in restricciones_qs
        ]

        return Response({
            # tarjeta destacada
            "residentes_sin_plan": sin_plan_lista,
            "residentes_sin_plan_count": len(sin_plan_lista),
            "residentes_activos_count": total_activos,
            "residentes_con_plan_count": con_plan_count,

            # métricas con listas
            "planes_pendientes": len(pendientes_lista),
            "planes_pendientes_lista": pendientes_lista,
            "planes_aprobados_vigentes": len(aprobados_lista),
            "planes_aprobados_lista": aprobados_lista,
            "alimentos_activos": len(alimentos_lista),
            "alimentos_lista": alimentos_lista,
            "restricciones_activas": len(restricciones_lista),
            "restricciones_lista": restricciones_lista,
        })
class PlantillaAsignadosView(APIView):
    """
    GET /api/plantillas/{id}/asignados/
    Lista los residentes con un plan VIGENTE originado en esta plantilla,
    indicando si tiene cambios (reemplazos) y cuáles.
    """

    permission_classes = [IsAdminOrCuidador]

    def get(self, request, pk):
        plantilla = get_object_or_404(PlantillaNutricional, pk=pk)

        # Comidas originales de la plantilla: {tipo_comida: (alimento_id, alimento_nombre)}
        comidas_plantilla = {
            c.tipo_comida: (c.alimento_id, c.alimento.nombre)
            for c in plantilla.comidas.select_related("alimento").all()
        }

        # Solo planes vigentes
        planes = (
            PlanNutricional.objects
            .filter(plantilla_origen=plantilla, estado="vigente")
            .select_related("residente")
            .prefetch_related("comidas__alimento")
        )

        resultado = []
        for plan in planes:
            # Primera comida copiada por tipo (la del momento de asignar)
            comidas_plan = {}
            for cd in plan.comidas.all():
                if cd.tipo_comida not in comidas_plan:
                    comidas_plan[cd.tipo_comida] = (cd.alimento_id, cd.alimento.nombre)

            # Detectar cambios por tipo de comida
            cambios = []
            for tipo, (alim_id_orig, alim_nombre_orig) in comidas_plantilla.items():
                actual = comidas_plan.get(tipo)
                if actual and actual[0] != alim_id_orig:
                    cambios.append({
                        "tipo_comida": tipo,
                        "original": alim_nombre_orig,
                        "reemplazo": actual[1],
                    })

            resultado.append({
                "plan_id": plan.id,
                "residente_id": plan.residente_id,
                "residente": f"{plan.residente.nombre} {plan.residente.apellido}",
                "fecha_inicio": str(plan.fecha_inicio),
                "con_cambios": len(cambios) > 0,
                "cambios": cambios,
            })

        resultado.sort(key=lambda x: x["fecha_inicio"], reverse=True)

        return Response({
            "total": len(resultado),
            "asignados": resultado,
        })
