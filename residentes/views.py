# ============================================================
# SPRINT 2 — Views completas
# Archivo NUEVO: residentes/views.py
# ============================================================

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from auditoria.mixins import AuditLogMixin

from .models import (
    Residente,
    HistorialMedico,
    ContactoEmergencia,
    ObservacionDiaria,
    TurnoMedico,
)
from .serializers import (
    ResidenteSerializer,
    ResidenteDetalleSerializer,
    ResidenteEditarSerializer,
    CambiarEstadoResidenteSerializer,
    ContactoEmergenciaSerializer,
    ContactoEmergenciaCreateSerializer,
    HistorialMedicoSerializer,
    ObservacionDiariaSerializer,
    TurnoMedicoSerializer,
)

# Importar los permisos personalizados del Sprint 1
from usuarios.permissions import IsAdministrador, IsAdminOrCuidador

# ============================================================
# T-19, T-20, T-21 — CRUD de Residentes
# ============================================================


class ResidenteListCreateView(APIView):
    """
    GET  /api/residentes/        → listar con filtros (T-20)
    POST /api/residentes/        → crear residente (T-19)
    """

    permission_classes = [IsAdminOrCuidador]

    def get(self, request):
        """
        T-20: Lista paginada con filtros opcionales por query params:
        ?nombre=   ?dni=   ?estado=
        """
        queryset = Residente.objects.all().order_by("apellido", "nombre")

        # Filtros opcionales — solo aplica si el parámetro viene en la URL
        nombre = request.query_params.get("nombre")
        dni = request.query_params.get("dni")
        estado = request.query_params.get("estado")

        if nombre:
            # icontains = contiene el texto, sin importar mayúsculas
            queryset = queryset.filter(nombre__icontains=nombre) | queryset.filter(
                apellido__icontains=nombre
            )
        if dni:
            queryset = queryset.filter(dni__icontains=dni)
        if estado:
            queryset = queryset.filter(estado=estado)

        # Paginación manual (page_size=20)
        page = int(request.query_params.get("page", 1))
        page_size = 20
        start = (page - 1) * page_size
        end = start + page_size

        total = queryset.count()
        pagina = queryset[start:end]

        serializer = ResidenteSerializer(pagina, many=True)
        return Response(
            {
                "total": total,
                "page": page,
                "pages": (total + page_size - 1) // page_size,
                "results": serializer.data,
            }
        )

    def post(self, request):
        """
        T-19: Crear residente.
        El signal post_save crea el HistorialMedico automáticamente.
        """
        serializer = ResidenteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Asignar automáticamente el usuario autenticado como registrado_por
        serializer.save(registrado_por=request.user)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ResidenteDetailView(APIView):
    """
    GET   /api/residentes/{id}/  → detalle completo (T-21)
    PUT   /api/residentes/{id}/  → edición total (T-22)
    PATCH /api/residentes/{id}/  → edición parcial (T-22)
    """

    permission_classes = [IsAdminOrCuidador]

    def get(self, request, pk):
        """T-21: Detalle completo con historial y contactos anidados."""
        residente = get_object_or_404(Residente, pk=pk)
        serializer = ResidenteDetalleSerializer(residente)
        return Response(serializer.data)

    def put(self, request, pk):
        """T-22: Edición total — solo Admin."""
        if not request.user.es_administrador:
            return Response(
                {"error": "Solo el Administrador puede editar residentes."},
                status=status.HTTP_403_FORBIDDEN,
            )
        residente = get_object_or_404(Residente, pk=pk)
        serializer = ResidenteEditarSerializer(residente, data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)

    def patch(self, request, pk):
        """T-22: Edición parcial — solo Admin."""
        if not request.user.es_administrador:
            return Response(
                {"error": "Solo el Administrador puede editar residentes."},
                status=status.HTTP_403_FORBIDDEN,
            )
        residente = get_object_or_404(Residente, pk=pk)
        # partial=True permite enviar solo los campos que cambiaron
        serializer = ResidenteEditarSerializer(
            residente, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)


class ResidenteEstadoView(APIView):
    """
    PATCH /api/residentes/{id}/estado/  → cambiar estado (T-23)
    """

    permission_classes = [IsAdminOrCuidador]

    def patch(self, request, pk):
        residente = get_object_or_404(Residente, pk=pk)
        serializer = CambiarEstadoResidenteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        residente.estado = serializer.validated_data["estado"]
        residente.save(update_fields=["estado", "updated_at"])

        return Response(
            {
                "mensaje": f"Estado actualizado a '{residente.estado}'.",
                "id": residente.pk,
                "estado": residente.estado,
            }
        )


# ============================================================
# T-24, T-25 — Contactos de Emergencia
# ============================================================


class ContactoEmergenciaView(APIView):
    """
    GET    /api/residentes/{id}/contactos/      → listar contactos
    POST   /api/residentes/{id}/contactos/      → crear contacto
    PATCH  /api/residentes/{id}/contactos/{cid}/ → editar contacto
    DELETE /api/residentes/{id}/contactos/{cid}/ → eliminar contacto
    """

    permission_classes = [IsAdminOrCuidador]

    def get(self, request, pk):
        residente = get_object_or_404(Residente, pk=pk)
        contactos = ContactoEmergencia.objects.filter(residente=residente)
        serializer = ContactoEmergenciaSerializer(contactos, many=True)
        return Response(serializer.data)

    def post(self, request, pk):
        residente = get_object_or_404(Residente, pk=pk)
        serializer = ContactoEmergenciaCreateSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        tipo = serializer.validated_data["tipo"]

        # Verificar el constraint UNIQUE(residente, tipo) antes de guardar
        # para dar un mensaje de error claro
        if ContactoEmergencia.objects.filter(residente=residente, tipo=tipo).exists():
            return Response(
                {"error": f"Este residente ya tiene un contacto de tipo '{tipo}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save(residente=residente)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ContactoEmergenciaDetailView(APIView):
    """
    PATCH  /api/residentes/{id}/contactos/{cid}/
    DELETE /api/residentes/{id}/contactos/{cid}/
    """

    permission_classes = [IsAdminOrCuidador]

    def patch(self, request, pk, cid):
        residente = get_object_or_404(Residente, pk=pk)
        contacto = get_object_or_404(ContactoEmergencia, pk=cid, residente=residente)
        serializer = ContactoEmergenciaCreateSerializer(
            contacto, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk, cid):
        residente = get_object_or_404(Residente, pk=pk)
        contacto = get_object_or_404(ContactoEmergencia, pk=cid, residente=residente)
        contacto.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ============================================================
# T-26, T-27, T-28 — Historial Médico
# ============================================================


class HistorialMedicoView(APIView):
    """
    GET   /api/residentes/{id}/historial/  → ver historial (T-26)
    PATCH /api/residentes/{id}/historial/  → editar historial (T-27)
    """

    permission_classes = [IsAdminOrCuidador]

    def get(self, request, pk):
        """T-26: Devuelve el historial médico completo del residente."""
        residente = get_object_or_404(Residente, pk=pk)
        # get_object_or_404 maneja el caso donde el historial no existe aún
        historial = get_object_or_404(HistorialMedico, residente=residente)
        serializer = HistorialMedicoSerializer(historial)
        return Response(serializer.data)

    def patch(self, request, pk):
        """
        T-27: Actualiza diagnósticos, alergias o condiciones_crónicas.
        Registra actualizado_por con el usuario autenticado.
        T-28: condiciones_cronicas persiste correctamente para Sprint 6.
        """
        residente = get_object_or_404(Residente, pk=pk)
        historial = get_object_or_404(HistorialMedico, residente=residente)

        serializer = HistorialMedicoSerializer(
            historial, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Asignar automáticamente quién hizo la última edición
        serializer.save(actualizado_por=request.user)

        return Response(serializer.data)


# SPRINT 3 — Views
# T-30, T-31, T-32, T-33 — Observaciones diarias


class ObservacionListCreateView(APIView):
    """
    GET  /api/residentes/{id}/observaciones/         → lista paginada (T-32)
    POST /api/residentes/{id}/observaciones/         → crear (T-30)
    """

    permission_classes = [IsAdminOrCuidador]

    def get(self, request, pk):
        """
        T-32: Lista ordenada de más reciente a más antigua.
        Filtro opcional: ?fecha=YYYY-MM-DD
        """
        residente = get_object_or_404(Residente, pk=pk)
        queryset = ObservacionDiaria.objects.filter(residente=residente).select_related(
            "registrado_por"
        )  # Evita N+1 queries

        # Filtro por fecha específica
        fecha = request.query_params.get("fecha")
        if fecha:
            queryset = queryset.filter(fecha_hora__date=fecha)

        # Paginación
        page = int(request.query_params.get("page", 1))
        page_size = 20
        start = (page - 1) * page_size
        end = start + page_size
        total = queryset.count()

        serializer = ObservacionDiariaSerializer(queryset[start:end], many=True)
        return Response(
            {
                "total": total,
                "page": page,
                "pages": (total + page_size - 1) // page_size,
                "results": serializer.data,
            }
        )

    def post(self, request, pk):
        """
        T-30: Crear observación.
        fecha_hora se genera automáticamente — se ignora si el cliente lo envía.
        """
        residente = get_object_or_404(Residente, pk=pk)
        serializer = ObservacionDiariaSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save(
            residente=residente,
            registrado_por=request.user,
            # fecha_hora NO se pasa — auto_now_add lo genera solo
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ObservacionDetailView(APIView):
    """
    GET /api/residentes/{id}/observaciones/{obs_id}/  → detalle (ST-31)
    """

    permission_classes = [IsAdminOrCuidador]

    def get(self, request, pk, obs_id):
        residente = get_object_or_404(Residente, pk=pk)
        observacion = get_object_or_404(
            ObservacionDiaria, pk=obs_id, residente=residente
        )
        serializer = ObservacionDiariaSerializer(observacion)
        return Response(serializer.data)


# ── T-35, T-36, T-37, T-38 — Turnos médicos ───────────────


class TurnoMedicoListCreateView(APIView):
    """
    GET  /api/residentes/{id}/turnos/  → listar turnos (T-36)
    POST /api/residentes/{id}/turnos/  → crear turno   (T-35)
    """

    permission_classes = [IsAdminOrCuidador]

    def get(self, request, pk):
        """
        T-36, T-37, T-38: Lista con filtros opcionales.
        ?tipo_consulta=urgencia
        ?fecha_desde=YYYY-MM-DD
        ?fecha_hasta=YYYY-MM-DD
        """
        residente = get_object_or_404(Residente, pk=pk)
        queryset = TurnoMedico.objects.filter(residente=residente).select_related(
            "registrado_por"
        )

        # T-37: filtro por tipo_consulta — valida que sea un valor válido
        tipo = request.query_params.get("tipo_consulta")
        if tipo:
            tipos_validos = [t[0] for t in TurnoMedico.TipoConsulta.choices]
            if tipo not in tipos_validos:
                return Response(
                    {"error": f"tipo_consulta inválido. Opciones: {tipos_validos}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            queryset = queryset.filter(tipo_consulta=tipo)

        # T-38: filtros por rango de fechas
        fecha_desde = request.query_params.get("fecha_desde")
        fecha_hasta = request.query_params.get("fecha_hasta")

        if fecha_desde:
            queryset = queryset.filter(fecha_hora__date__gte=fecha_desde)
        if fecha_hasta:
            queryset = queryset.filter(fecha_hora__date__lte=fecha_hasta)

        serializer = TurnoMedicoSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request, pk):
        """T-35: Crear turno médico. Solo admin puede registrar."""
        if not request.user.es_administrador:
            return Response(
                {"error": "Solo el Administrador puede registrar turnos médicos."},
                status=status.HTTP_403_FORBIDDEN,
            )

        residente = get_object_or_404(Residente, pk=pk)
        serializer = TurnoMedicoSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save(residente=residente, registrado_por=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
