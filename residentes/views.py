
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from auditoria.mixins import AuditLogMixin, serializar_instancia, registrar_auditoria
from django.db import models
from datetime import date
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
    ObservacionDiariaEditarSerializer,
    TurnoMedicoSerializer,
)

# Importar los permisos personalizados del Sprint 1
from usuarios.permissions import IsAdministrador, IsAdminOrCuidador

# ============================================================
# T-19, T-20, T-21 — CRUD de Residentes
# ============================================================


class ResidenteListCreateView(AuditLogMixin, APIView):
    """
    GET  /api/residentes/        → listar con filtros (T-20)
    POST /api/residentes/        → crear residente (T-19)
    """

    # A1 - Declarar auditoria
    audit_entidad = "residentes"

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

        # === PAGINACIÓN CONFIGURABLE ===
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        
        # Seguridad: límite máximo de registros por página
        page_size = min(max(page_size, 1), 200)

        start = (page - 1) * page_size
        end = start + page_size

        total = queryset.count()
        pagina = queryset[start:end]

        serializer = ResidenteSerializer(pagina, many=True)
        
        return Response({
            "count": total,           # Estándar DRF
            "total": total,           # Compatibilidad con tu frontend
            "page": page,
            "pages": (total + page_size - 1) // page_size,
            "page_size": page_size,   # ← Importante para el frontend
            "results": serializer.data,
        })

    def post(self, request):
        """
        T-19: Crear residente.
        El signal post_save crea el HistorialMedico automáticamente.
        """
        serializer = ResidenteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Asignar automáticamente el usuario autenticado como registrado_por
        residente = serializer.save(registrado_por=request.user)

        # A3 - Registrar auditoría de creación
        self.audit_crear(request, residente)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

class ResidenteDetailView(AuditLogMixin, APIView):
    """
    GET   /api/residentes/{id}/  → detalle completo (T-21)
    PUT   /api/residentes/{id}/  → edición total (T-22)
    PATCH /api/residentes/{id}/  → edición parcial (T-22)
    """

    # A1 - Declarar auditoria
    audit_entidad = "residentes"

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
        
        # A2 - snapshot
        antes = serializar_instancia(residente)

        serializer = ResidenteEditarSerializer(residente, data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save()

        # A3 - registrar
        residente.refresh_from_db()
        self.audit_editar(request, antes, residente)

        return Response(serializer.data)

    def patch(self, request, pk):
        """T-22: Edición parcial — solo Admin."""
        if not request.user.es_administrador:
            return Response(
                {"error": "Solo el Administrador puede editar residentes."},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        residente = get_object_or_404(Residente, pk=pk)
        
        # A2 - snapshot
        antes = serializar_instancia(residente)

        # partial=True permite enviar solo los campos que cambiaron
        serializer = ResidenteEditarSerializer(
            residente, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save()

        # A3 - registrar
        residente.refresh_from_db()
        self.audit_editar(request, antes, residente)

        return Response(serializer.data)

class ResidenteEstadoView(AuditLogMixin, APIView):
    """
    PATCH /api/residentes/{id}/estado/  → cambiar estado (T-23)
    """

    # A1 - Declarar auditoria
    audit_entidad = "residentes"

    permission_classes = [IsAdminOrCuidador]

    def patch(self, request, pk):
        residente = get_object_or_404(Residente, pk=pk)
        
        # A2 - snapshot
        antes = serializar_instancia(residente)

        serializer = CambiarEstadoResidenteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        residente.estado = serializer.validated_data["estado"]
        residente.save(update_fields=["estado", "updated_at"])

        # A3 - registrar
        self.audit_editar(request, antes, residente)

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


class ContactoEmergenciaView(AuditLogMixin, APIView):
    """
    GET    /api/residentes/{id}/contactos/      → listar contactos
    POST   /api/residentes/{id}/contactos/      → crear contacto
    PATCH  /api/residentes/{id}/contactos/{cid}/ → editar contacto
    DELETE /api/residentes/{id}/contactos/{cid}/ → eliminar contacto
    """

    audit_entidad = "contactos_emergencia"
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

        contacto = serializer.save(residente=residente)

        # AUDITORÍA: registrar creación de contacto
        self.audit_crear(request, contacto)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ContactoEmergenciaDetailView(AuditLogMixin, APIView):
    """
    PATCH  /api/residentes/{id}/contactos/{cid}/
    DELETE /api/residentes/{id}/contactos/{cid}/
    """

    audit_entidad = "contactos_emergencia"
    permission_classes = [IsAdminOrCuidador]

    def patch(self, request, pk, cid):
        residente = get_object_or_404(Residente, pk=pk)
        contacto = get_object_or_404(ContactoEmergencia, pk=cid, residente=residente)

        # AUDITORÍA: snapshot ANTES de editar
        antes = serializar_instancia(contacto)

        serializer = ContactoEmergenciaCreateSerializer(
            contacto, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()

        # AUDITORÍA: registrar edición con snapshot antes/después
        contacto.refresh_from_db()
        self.audit_editar(request, antes, contacto)

        return Response(serializer.data)

    def delete(self, request, pk, cid):
        residente = get_object_or_404(Residente, pk=pk)
        contacto = get_object_or_404(ContactoEmergencia, pk=cid, residente=residente)

        # AUDITORÍA: snapshot ANTES de borrar (es un borrado real)
        antes = serializar_instancia(contacto)
        contacto_pk = contacto.pk

        contacto.delete()

        # AUDITORÍA: registrar eliminación de contacto
        registrar_auditoria(
            request=request,
            accion="eliminar",
            entidad_nombre=self.audit_entidad,
            entidad_id=contacto_pk,
            datos_anteriores=antes,
            datos_nuevos=None,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


# ============================================================
# T-26, T-27, T-28 — Historial Médico
# ============================================================


class HistorialMedicoView(AuditLogMixin, APIView):
    """
    GET   /api/residentes/{id}/historial/  → ver historial (T-26)
    PATCH /api/residentes/{id}/historial/  → editar historial (T-27)
    """

    audit_entidad = "historial_medico"
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

        # AUDITORÍA: snapshot ANTES de editar (datos médicos sensibles)
        antes = serializar_instancia(historial)

        serializer = HistorialMedicoSerializer(
            historial, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Asignar automáticamente quién hizo la última edición
        serializer.save(actualizado_por=request.user)

        # AUDITORÍA: registrar edición con snapshot antes/después
        historial.refresh_from_db()
        self.audit_editar(request, antes, historial)

        return Response(serializer.data)


# SPRINT 3 — Views
# T-30, T-31, T-32, T-33 — Observaciones diarias


class ObservacionListCreateView(AuditLogMixin, APIView):
    """
    GET  /api/residentes/{id}/observaciones/         → lista paginada (T-32)
    POST /api/residentes/{id}/observaciones/         → crear (T-30)
    """

    audit_entidad = "observaciones_diarias"
    permission_classes = [IsAdminOrCuidador]

    def get(self, request, pk):
        """
        Lista de más reciente a más antigua, paginada.
        Filtros: ?fecha=YYYY-MM-DD  ?buscar=texto  ?page=  ?page_size=
        """
        residente = get_object_or_404(Residente, pk=pk)
        queryset = ObservacionDiaria.objects.filter(
            residente=residente
        ).select_related("registrado_por")

        fecha = request.query_params.get("fecha")
        if fecha:
            queryset = queryset.filter(fecha_hora__date=fecha)

        # Búsqueda en el contenido
        buscar = request.query_params.get("buscar")
        if buscar:
            queryset = queryset.filter(
                models.Q(estado_fisico__icontains=buscar)
                | models.Q(estado_emocional__icontains=buscar)
            )

        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 10))
        page_size = min(max(page_size, 1), 200)
        start = (page - 1) * page_size
        end = start + page_size
        total = queryset.count()

        serializer = ObservacionDiariaSerializer(queryset[start:end], many=True)
        return Response({
            "count": total,
            "total": total,
            "page": page,
            "pages": (total + page_size - 1) // page_size,
            "page_size": page_size,
            "results": serializer.data,
        })

    def post(self, request, pk):
        """
        T-30: Crear observación.
        fecha_hora se genera automáticamente — se ignora si el cliente lo envía.
        """
        residente = get_object_or_404(Residente, pk=pk)
        serializer = ObservacionDiariaSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        observacion = serializer.save(
            residente=residente,
            registrado_por=request.user,
            # fecha_hora NO se pasa — auto_now_add lo genera solo
        )

        # AUDITORÍA: registrar creación de observación
        self.audit_crear(request, observacion)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ObservacionDetailView(AuditLogMixin, APIView):
    """
    GET   /api/residentes/{id}/observaciones/{obs_id}/  → detalle (ST-31)
    PATCH /api/residentes/{id}/observaciones/{obs_id}/  → editar contenido
    Regla: solo el autor de la observación o un administrador pueden editar.
    La fecha y el autor NO cambian nunca.
    """

    audit_entidad = "observaciones_diarias"
    permission_classes = [IsAdminOrCuidador]

    def get(self, request, pk, obs_id):
        residente = get_object_or_404(Residente, pk=pk)
        observacion = get_object_or_404(
            ObservacionDiaria, pk=obs_id, residente=residente
        )
        serializer = ObservacionDiariaSerializer(observacion)
        return Response(serializer.data)

    def patch(self, request, pk, obs_id):
        residente = get_object_or_404(Residente, pk=pk)
        observacion = get_object_or_404(
            ObservacionDiaria, pk=obs_id, residente=residente
        )

        if observacion.registrado_por_id != request.user.id:
            return Response(
                {"error": "Solo puedes editar tus propias observaciones."},
             status=status.HTTP_403_FORBIDDEN,
        )

        # Regla de autoría: solo el autor o el admin pueden editar
        es_autor = observacion.registrado_por_id == request.user.id
        if not (es_autor or request.user.es_administrador):
            return Response(
                {"error": "Solo el autor de la observación o el administrador pueden editarla."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # AUDITORÍA: snapshot ANTES de editar
        antes = serializar_instancia(observacion)

        serializer = ObservacionDiariaEditarSerializer(
            observacion, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()  # NO se pasa registrado_por ni fecha_hora → quedan intactos

        # AUDITORÍA: registrar edición con snapshot antes/después
        observacion.refresh_from_db()
        self.audit_editar(request, antes, observacion)

        # Devolvemos el objeto completo (con autor y fecha) para refrescar la UI
        return Response(ObservacionDiariaSerializer(observacion).data)

class TurnoMedicoListCreateView(AuditLogMixin, APIView):
    """
    GET  /api/residentes/{id}/turnos/  → listar turnos (paginado, filtros)
    POST /api/residentes/{id}/turnos/  → crear turno (solo admin)
    """

    audit_entidad = "turnos_medicos"
    permission_classes = [IsAdminOrCuidador]

    def get(self, request, pk):
        """
        Filtros: ?tipo_consulta=  ?fecha_desde=  ?fecha_hasta=  ?buscar=
        Paginación: ?page=  ?page_size=
        """
        residente = get_object_or_404(Residente, pk=pk)
        queryset = TurnoMedico.objects.filter(residente=residente).select_related(
            "registrado_por"
        )

        tipo = request.query_params.get("tipo_consulta")
        if tipo:
            tipos_validos = [t[0] for t in TurnoMedico.TipoConsulta.choices]
            if tipo not in tipos_validos:
                return Response(
                    {"error": f"tipo_consulta inválido. Opciones: {tipos_validos}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            queryset = queryset.filter(tipo_consulta=tipo)

        fecha_desde = request.query_params.get("fecha_desde")
        fecha_hasta = request.query_params.get("fecha_hasta")
        if fecha_desde:
            queryset = queryset.filter(fecha_hora__date__gte=fecha_desde)
        if fecha_hasta:
            queryset = queryset.filter(fecha_hora__date__lte=fecha_hasta)

        buscar = request.query_params.get("buscar")
        if buscar:
            queryset = queryset.filter(observaciones__icontains=buscar)

        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 10))
        page_size = min(max(page_size, 1), 200)
        start = (page - 1) * page_size
        end = start + page_size
        total = queryset.count()

        serializer = TurnoMedicoSerializer(queryset[start:end], many=True)
        return Response({
            "count": total,
            "total": total,
            "page": page,
            "pages": (total + page_size - 1) // page_size,
            "page_size": page_size,
            "results": serializer.data,
        })

    def post(self, request, pk):
        """Crear turno médico. Solo admin."""
        if not request.user.es_administrador:
            return Response(
                {"error": "Solo el Administrador puede registrar turnos médicos."},
                status=status.HTTP_403_FORBIDDEN,
            )

        residente = get_object_or_404(Residente, pk=pk)
        serializer = TurnoMedicoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        turno = serializer.save(residente=residente, registrado_por=request.user)

        # AUDITORÍA: registrar creación de turno médico
        self.audit_crear(request, turno)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class TurnoMedicoDetailView(AuditLogMixin, APIView):
    """
    GET   /api/residentes/{id}/turnos/{turno_id}/  → detalle
    PATCH /api/residentes/{id}/turnos/{turno_id}/  → editar (solo admin)
    """

    audit_entidad = "turnos_medicos"
    permission_classes = [IsAdminOrCuidador]

    def get(self, request, pk, turno_id):
        residente = get_object_or_404(Residente, pk=pk)
        turno = get_object_or_404(TurnoMedico, pk=turno_id, residente=residente)
        return Response(TurnoMedicoSerializer(turno).data)

    def patch(self, request, pk, turno_id):
        residente = get_object_or_404(Residente, pk=pk)
        turno = get_object_or_404(TurnoMedico, pk=turno_id, residente=residente)

        # Solo admin puede tocar turnos, y solo si es el autor del turno
        if not request.user.es_administrador:
            return Response(
                {"error": "Solo el Administrador puede editar turnos médicos."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if turno.registrado_por_id != request.user.id:
            return Response(
                {"error": "Solo puedes editar los turnos que tú registraste."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # AUDITORÍA: snapshot ANTES de editar
        antes = serializar_instancia(turno)

        serializer = TurnoMedicoSerializer(turno, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()

        # AUDITORÍA: registrar edición con snapshot antes/después
        turno.refresh_from_db()
        self.audit_editar(request, antes, turno)

        return Response(serializer.data)


class ResumenDashboardResidentesView(APIView):
    """
    GET /api/residentes/resumen-dashboard/
    Métricas y listas de residentes para la sección del dashboard.
    """
    permission_classes = [IsAdminOrCuidador]

    def get(self, request):
        hoy = date.today()

        activos        = Residente.objects.filter(estado=Residente.Estado.ACTIVO)
        hospitalizados = Residente.objects.filter(estado=Residente.Estado.HOSPITALIZADO)
        dados_de_alta  = Residente.objects.filter(estado=Residente.Estado.DADO_DE_ALTA)

        # Ingresos del mes actual (residentes que ingresaron este mes)
        ingresos_mes = Residente.objects.filter(
            fecha_ingreso__year=hoy.year,
            fecha_ingreso__month=hoy.month,
        )

        def serializar(qs):
            # Lista ligera: nombre completo + dato extra
            return [
                {
                    "nombre": f"{r.nombre} {r.apellido}",
                    "dni": r.dni,
                    "ingreso": r.fecha_ingreso.isoformat(),
                }
                for r in qs.order_by("apellido", "nombre")
            ]

        return Response({
            "activos_count":        activos.count(),
            "hospitalizados_count": hospitalizados.count(),
            "dados_de_alta_count":  dados_de_alta.count(),
            "ingresos_mes_count":   ingresos_mes.count(),
            "total":                Residente.objects.count(),

            "activos_lista":        serializar(activos),
            "hospitalizados_lista": serializar(hospitalizados),
            "dados_de_alta_lista":  serializar(dados_de_alta),
            "ingresos_mes_lista":   serializar(ingresos_mes),
        })
