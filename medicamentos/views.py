from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from auditoria.mixins import AuditLogMixin, serializar_instancia

# Necesario para el F() en get_alertas_stock
from django.db import models

from .models import (
    CatalogoMedicamento,
    StockMedicamento,
    ResidenteMedicamento,
    AdministracionMedicamento,
    MovimientoStock,
)
from .serializers import (
    CatalogoMedicamentoSerializer,
    CatalogoMedicamentoEditarSerializer,
    StockMedicamentoSerializer,
    ResidenteMedicamentoSerializer,
    AdministracionMedicamentoSerializer,
    MovimientoStockSerializer,
)
from django.db import transaction
from .stock_service import (
    descontar_por_administracion,
    revertir_administracion,
    StockInsuficienteError,
)

from usuarios.permissions import IsAdministrador, IsAdminOrCuidador
from residentes.models import Residente
from datetime import datetime, timedelta


# ── T-40, T-41 — CRUD Catálogo ─────────────────────────────

class MedicamentoListCreateView(AuditLogMixin, APIView):
    """
    GET  /api/medicamentos/  → listar activos (todos los roles)
    POST /api/medicamentos/  → crear (solo Admin)
    """

    audit_entidad = "medicamentos"

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdministrador()]
        return [IsAdminOrCuidador()]

    def get(self, request):
        incluir_archivados = request.query_params.get("incluir_archivados", "false")
        if incluir_archivados.lower() == "true":
            queryset = CatalogoMedicamento.objects.all()
        else:
            queryset = CatalogoMedicamento.objects.filter(estado="activo")

        nombre = request.query_params.get("nombre")
        if nombre:
            queryset = queryset.filter(nombre_comercial__icontains=nombre)

        # Orden descendente por fecha de última actualización
        queryset = queryset.order_by("-updated_at")

        serializer = CatalogoMedicamentoSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = CatalogoMedicamentoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        instancia = serializer.save(creado_por=request.user)

        # AUDITORÍA: registrar creación de medicamento
        self.audit_crear(request, instancia)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MedicamentoDetailView(AuditLogMixin, APIView):
    """
    GET        /api/medicamentos/{id}/          → detalle
    PUT/PATCH  /api/medicamentos/{id}/          → editar (solo Admin)
    """

    audit_entidad = "medicamentos"

    def get_permissions(self):
        if self.request.method in ["PUT", "PATCH"]:
            return [IsAdministrador()]
        return [IsAdminOrCuidador()]

    def get(self, request, pk):
        medicamento = get_object_or_404(CatalogoMedicamento, pk=pk)
        serializer = CatalogoMedicamentoSerializer(medicamento)
        return Response(serializer.data)

    def patch(self, request, pk):
        medicamento = get_object_or_404(CatalogoMedicamento, pk=pk)

        # AUDITORÍA: snapshot del estado ANTES de modificar
        antes = serializar_instancia(medicamento)

        # Corrección 1: si está archivado, solo se permite editar observaciones
        if medicamento.estado == "archivado":
            campos = set(request.data.keys())
            if campos - {"observaciones"}:
                return Response(
                    {"error": "El medicamento está archivado: solo se pueden editar las observaciones."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = CatalogoMedicamentoEditarSerializer(
            medicamento, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()

        # AUDITORÍA: registrar edición con snapshot antes/después
        medicamento.refresh_from_db()
        self.audit_editar(request, antes, medicamento)

        return Response(CatalogoMedicamentoSerializer(medicamento).data)


class MedicamentoArchivarView(AuditLogMixin, APIView):
    audit_entidad = "medicamentos"
    permission_classes = [IsAdministrador]

    def patch(self, request, pk):
        medicamento = get_object_or_404(CatalogoMedicamento, pk=pk)

        if medicamento.estado == "archivado":
            return Response(
                {"error": "Este medicamento ya está archivado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        antes = serializar_instancia(medicamento)

        medicamento.estado = "archivado"
        medicamento.save(update_fields=["estado"])

        self.audit_editar(request, antes, medicamento)

        return Response({
            "mensaje": f"'{medicamento.nombre_comercial}' archivado correctamente.",
            "id": medicamento.pk,
            "estado": medicamento.estado,
        })


# ── T-43, T-44 — Stock por lote ────────────────────────────

class StockListCreateView(AuditLogMixin, APIView):

    audit_entidad = "stock_medicamentos"

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdministrador()]
        return [IsAdminOrCuidador()]

    def get(self, request, pk):
        medicamento = get_object_or_404(CatalogoMedicamento, pk=pk)
        lotes = StockMedicamento.objects.filter(medicamento=medicamento).select_related("actualizado_por")
        serializer = StockMedicamentoSerializer(lotes, many=True)
        return Response(serializer.data)

    def post(self, request, pk):
        medicamento = get_object_or_404(CatalogoMedicamento, pk=pk)
        data = request.data.copy()
        # Corrección 1: la unidad siempre es la forma farmacéutica del medicamento
        data["unidad"] = medicamento.forma_farmaceutica
        serializer = StockMedicamentoSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        lote = serializer.save(
            medicamento=medicamento,
            actualizado_por=request.user,
            unidad=medicamento.forma_farmaceutica
        )

        # AUDITORÍA: registrar creación del lote de stock
        self.audit_crear(request, lote)

        if lote.cantidad > 0:
            MovimientoStock.objects.create(
                lote=lote,
                medicamento=medicamento,
                tipo=MovimientoStock.Tipo.ENTRADA,
                cantidad=lote.cantidad,
                motivo="Ingreso de nuevo lote",
                realizado_por=request.user,
            )

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class StockDetailView(AuditLogMixin, APIView):
    """
    PATCH /api/medicamentos/{id}/stock/{lote_id}/  → actualizar cantidad/umbral (T-43)
    """

    audit_entidad = "stock_medicamentos"

    def get_permissions(self):
        # Editar observaciones lo puede hacer cualquier rol;
        # el resto de campos solo admin (validado dentro del patch).
        return [IsAdminOrCuidador()]

    def patch(self, request, pk, lote_id):
        medicamento = get_object_or_404(CatalogoMedicamento, pk=pk)
        lote = get_object_or_404(StockMedicamento, pk=lote_id, medicamento=medicamento)

        # AUDITORÍA: snapshot del lote ANTES de cualquier cambio
        antes = serializar_instancia(lote)

        data = request.data.copy()
        # La unidad nunca se edita aquí (va enlazada a la forma farmacéutica)
        data.pop("unidad", None)

        # Corrección 3: si el medicamento está archivado, SOLO se permite observaciones
        if medicamento.estado == "archivado":
            campos_permitidos = {"observaciones"}
            enviados = set(data.keys())
            no_permitidos = enviados - campos_permitidos
            if no_permitidos:
                return Response(
                    {"error": "El medicamento está archivado: solo se pueden editar las observaciones del lote."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            serializer = StockMedicamentoSerializer(lote, data=data, partial=True)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            serializer.save(actualizado_por=request.user)

            # AUDITORÍA: edición de observaciones (medicamento archivado)
            lote.refresh_from_db()
            self.audit_editar(request, antes, lote)

            return Response(serializer.data)

        # Medicamento activo: solo admin puede editar el resto de campos
        if request.user.rol != "administrador":
            return Response(
                {"error": "Solo el administrador puede editar los datos del lote."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # No editable si el lote ya tuvo salidas por administración
        ya_administrado = lote.movimientos.filter(
            tipo="salida", administracion__isnull=False
        ).exists()
        # Permitimos editar observaciones aunque ya se haya administrado
        editando_solo_observaciones = set(data.keys()) <= {"observaciones"}
        if ya_administrado and not editando_solo_observaciones:
            return Response(
                {"error": "No se puede editar este lote: ya tiene medicamentos administrados."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cantidad_antes = lote.cantidad
        serializer = StockMedicamentoSerializer(lote, data=data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save(actualizado_por=request.user)

        diferencia = lote.cantidad - cantidad_antes
        if diferencia != 0:
            MovimientoStock.objects.create(
                lote=lote,
                medicamento=medicamento,
                tipo=MovimientoStock.Tipo.ENTRADA if diferencia > 0 else MovimientoStock.Tipo.SALIDA,
                cantidad=abs(diferencia),
                motivo="Corrección manual de stock (admin)",
                realizado_por=request.user,
            )

        # AUDITORÍA: edición del lote (medicamento activo)
        lote.refresh_from_db()
        self.audit_editar(request, antes, lote)

        return Response(serializer.data)


class MovimientoStockHistorialView(APIView):
    """
    GET /api/medicamentos/{id}/movimientos/  → historial de movimientos del medicamento
    Filtros opcionales: ?tipo=entrada|salida|devolucion
    """

    permission_classes = [IsAdminOrCuidador]

    def get(self, request, pk):
        medicamento = get_object_or_404(CatalogoMedicamento, pk=pk)

        queryset = MovimientoStock.objects.filter(
            medicamento=medicamento
        ).select_related("lote", "realizado_por")

        tipo = request.query_params.get("tipo")
        if tipo in ("entrada", "salida", "devolucion"):
            queryset = queryset.filter(tipo=tipo)

        # Paginación
        page = int(request.query_params.get("page", 1))
        page_size = 20
        start = (page - 1) * page_size
        end = start + page_size
        total = queryset.count()
        pagina = queryset[start:end]

        serializer = MovimientoStockSerializer(pagina, many=True)
        return Response(
            {
                "total": total,
                "page": page,
                "pages": (total + page_size - 1) // page_size,
                "results": serializer.data,
            }
        )


# ── T-45, T-46 — Alertas de stock ─────────────────────────


def get_alertas_stock():
    """
    T-46: Función de servicio reutilizable.
    Retorna lotes con stock_bajo O vencimiento_proximo.
    Se usará en el dashboard del Sprint 9.
    """
    hoy = timezone.now().date()
    limite = hoy + timedelta(days=30)
    alertas = []

    lotes = StockMedicamento.objects.select_related(
        "medicamento", "actualizado_por"
    ).filter(
        # stock bajo O vencimiento próximo
        cantidad__lte=models.F("umbral_minimo")
    ) | StockMedicamento.objects.select_related(
        "medicamento", "actualizado_por"
    ).filter(
        fecha_vencimiento__lte=limite
    )

    # Eliminar duplicados (un lote puede tener ambas alertas)
    lotes_vistos = set()
    for lote in lotes:
        if lote.pk in lotes_vistos:
            continue
        lotes_vistos.add(lote.pk)

        tipos = []
        if lote.cantidad <= lote.umbral_minimo:
            tipos.append("stock_bajo")
        if lote.fecha_vencimiento <= limite:
            tipos.append("vencimiento_proximo")

        alertas.append(
            {
                "lote_id": lote.pk,
                "lote": lote.lote,
                "medicamento_id": lote.medicamento.pk,
                "medicamento": lote.medicamento.nombre_comercial,
                "cantidad": lote.cantidad,
                "umbral_minimo": lote.umbral_minimo,
                "fecha_vencimiento": lote.fecha_vencimiento,
                "tipos_alerta": tipos,
            }
        )

    return alertas


class AlertasStockView(APIView):
    """
    GET /api/alertas/stock/  → lotes con stock bajo o vencimiento próximo (T-45)
    """

    permission_classes = [IsAdminOrCuidador]

    def get(self, request):
        alertas = get_alertas_stock()
        return Response(
            {
                "total": len(alertas),
                "alertas": alertas,
            }
        )


class PrescripcionListCreateView(AuditLogMixin, APIView):
    """
    GET  /api/residentes/{id}/medicamentos/  → listar prescripciones activas (T-50)
    POST /api/residentes/{id}/medicamentos/  → crear prescripción (T-49)
    """

    # A1 - Declarar auditoria
    audit_entidad = "prescripciones"

    permission_classes = [IsAdminOrCuidador]

    def get(self, request, pk):
        residente = get_object_or_404(Residente, pk=pk)
        # Por defecto solo activas — con ?incluir_finalizadas=true muestra todas
        incluir = request.query_params.get("incluir_finalizadas", "false")
        if incluir.lower() == "true":
            queryset = ResidenteMedicamento.objects.filter(residente=residente)
        else:
            queryset = ResidenteMedicamento.objects.filter(
                residente=residente, estado="activo"
            )
        queryset = queryset.select_related("medicamento", "prescrito_por")
        serializer = ResidenteMedicamentoSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request, pk):
        """
        T-49: Crear prescripción.
        Valida que medicamento esté activo.
        Verifica contraindicaciones contra condiciones_cronicas del residente (RF-10-B).
        """
        residente = get_object_or_404(Residente, pk=pk)

        if residente.estado == 'dado_de_alta':
            return Response(
                {"error": "No se puede prescribir medicamentos a un residente dado de alta."},
                status=status.HTTP_400_BAD_REQUEST
            )
        # ========================

        serializer = ResidenteMedicamentoSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        medicamento = serializer.validated_data["medicamento"]

        # RF-10-B: verificar contraindicaciones vs condiciones crónicas del residente
        advertencias = []
        try:
            historial = residente.historial_medico
            if historial.condiciones_cronicas and medicamento.contraindicaciones:
                # Búsqueda simple de palabras clave en común
                condiciones = historial.condiciones_cronicas.lower()
                contraindicaciones = medicamento.contraindicaciones.lower()
                palabras = [
                    p.strip() for p in condiciones.split(",") if len(p.strip()) > 3
                ]
                for palabra in palabras:
                    if palabra in contraindicaciones:
                        advertencias.append(
                            f"Posible contraindicación: '{palabra}' aparece en las contraindicaciones del medicamento."
                        )
        except Exception:
            pass

        prescripcion = serializer.save(residente=residente, prescrito_por=request.user)

        # A3 - Registrar auditoría de creación
        self.audit_crear(request, prescripcion)

        response_data = serializer.data
        if advertencias:
            response_data = dict(serializer.data)
            response_data["advertencias"] = advertencias

        return Response(response_data, status=status.HTTP_201_CREATED)

# ── T-48, T-49, T-50 — Prescripciones ─────────────────────


class PrescripcionDetailView(AuditLogMixin, APIView):
    """
    PATCH /api/residentes/{id}/medicamentos/{pm_id}/          → editar (T-50)
    PATCH /api/residentes/{id}/medicamentos/{pm_id}/finalizar/ → finalizar (T-50)
    """

    audit_entidad = "prescripciones"

    permission_classes = [IsAdminOrCuidador]

    def patch(self, request, pk, pm_id):
        residente = get_object_or_404(Residente, pk=pk)
        prescripcion = get_object_or_404(
            ResidenteMedicamento, pk=pm_id, residente=residente
        )

        # Ajuste 1: solo el administrador puede editar
        if request.user.rol != 'administrador':
            return Response(
                {"error": "Solo el administrador puede editar una prescripción."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Ajuste 1: no se puede editar si ya está finalizada
        if prescripcion.estado == 'finalizado':
            return Response(
                {"error": "No se puede editar una prescripción finalizada."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Ajuste 1: no se puede editar si ya tiene administraciones registradas
        if prescripcion.administraciones.exists():
            return Response(
                {"error": "No se puede editar: la prescripción ya tiene tomas registradas."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # AUDITORÍA: snapshot ANTES de editar
        antes = serializar_instancia(prescripcion)

        serializer = ResidenteMedicamentoSerializer(
            prescripcion, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()

        # AUDITORÍA: registrar edición con snapshot antes/después
        prescripcion.refresh_from_db()
        self.audit_editar(request, antes, prescripcion)

        return Response(serializer.data)


class PrescripcionFinalizarView(AuditLogMixin, APIView):
    """PATCH /api/residentes/{id}/medicamentos/{pm_id}/finalizar/"""

    audit_entidad = "prescripciones"

    permission_classes = [IsAdminOrCuidador]

    def patch(self, request, pk, pm_id):
        residente = get_object_or_404(Residente, pk=pk)
        prescripcion = get_object_or_404(
            ResidenteMedicamento, pk=pm_id, residente=residente
        )
        if prescripcion.estado == "finalizado":
            return Response(
                {"error": "Esta prescripción ya está finalizada."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # AUDITORÍA: snapshot ANTES de finalizar
        antes = serializar_instancia(prescripcion)

        prescripcion.estado = "finalizado"
        if not prescripcion.fecha_fin:
            prescripcion.fecha_fin = timezone.now().date()
        prescripcion.save()

        # AUDITORÍA: registrar finalización (cambio de estado)
        self.audit_editar(request, antes, prescripcion)

        return Response(
            {
                "mensaje": "Prescripción finalizada correctamente.",
                "id": prescripcion.pk,
                "estado": prescripcion.estado,
                "fecha_fin": prescripcion.fecha_fin,
            }
        )


# ── T-51, T-52, T-53 — Administraciones ───────────────────


class AdministracionCreateView(AuditLogMixin, APIView):
    """
    POST /api/administraciones/  → registrar toma (T-52)
    Si administrado=True, descuenta stock por FEFO y registra el movimiento.
    Si no hay stock suficiente, bloquea con 400 y NO crea la administración.
    """

    audit_entidad = "administraciones_medicamento"

    permission_classes = [IsAdminOrCuidador]

    def post(self, request):
        serializer = AdministracionMedicamentoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        pm = serializer.validated_data['residente_medicamento']
        if pm.estado == 'finalizado':
            return Response(
                {"error": "No se puede registrar una toma de una prescripción finalizada."},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Ajuste 6: no permitir administrar un medicamento archivado
        if pm.medicamento.estado == 'archivado':
            return Response(
                {"error": f"El medicamento '{pm.medicamento.nombre_comercial}' está archivado y no puede administrarse. Reactívalo o finaliza la prescripción."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        administrado = serializer.validated_data.get('administrado', True)

        # Todo dentro de una transacción: si el descuento falla, no queda
        # ni la administración ni el movimiento a medias.
        try:
            with transaction.atomic():
                administracion = serializer.save(realizado_por=request.user)

                # Solo descontamos si efectivamente se administró
                if administrado:
                    descontar_por_administracion(administracion, request.user, cantidad=1)
        except StockInsuficienteError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # AUDITORÍA: la transacción ya hizo commit con éxito.
        # Se registra FUERA del atomic() para no anidar el log en la
        # transacción de stock y para no afectar el descuento si fallara.
        self.audit_crear(request, administracion)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdministracionDetailView(AuditLogMixin, APIView):
    """
    PATCH /api/administraciones/{id}/  → corregir registro (T-53)
    Admin y cuidador, solo dentro de las primeras 2 horas, solo una vez,
    y únicamente sobre las administraciones que el propio usuario registró.
    Si la corrección cambia administrado True→False, devuelve el stock.
    Si cambia False→True, descuenta el stock (FEFO).
    """

    audit_entidad = "administraciones_medicamento"

    permission_classes = [IsAdminOrCuidador]

    def patch(self, request, adm_id):
        administracion = get_object_or_404(AdministracionMedicamento, pk=adm_id)

        # Cada usuario solo puede corregir SUS propias administraciones
        if administracion.realizado_por_id != request.user.id:
            return Response(
                {"error": "Solo puedes corregir las administraciones que tú registraste."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # T-53: corrección solo dentro de las primeras 2 horas
        limite = administracion.fecha_hora_programada + timedelta(hours=2)
        if timezone.now() > limite:
            return Response(
                {
                    "error": "Solo se puede corregir un registro dentro de las 2 horas siguientes a la toma programada."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Solo se permite corregir UNA vez
        if administracion.corregida:
            return Response(
                {"error": "Esta toma ya fue corregida una vez y no puede corregirse de nuevo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Guardamos el estado ANTES de aplicar cambios
        administrado_antes = administracion.administrado

        # AUDITORÍA: snapshot completo ANTES de la corrección
        antes = serializar_instancia(administracion)

        serializer = AdministracionMedicamentoSerializer(
            administracion, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        administrado_despues = serializer.validated_data.get(
            "administrado", administrado_antes
        )

        try:
            with transaction.atomic():
                # Guardamos y marcamos como corregida en el mismo save
                serializer.save(corregida=True)

                # Administrada → Omitida: devolver stock
                if administrado_antes and not administrado_despues:
                    revertir_administracion(administracion, request.user)

                # Omitida → Administrada: descontar stock
                elif not administrado_antes and administrado_despues:
                    descontar_por_administracion(administracion, request.user, cantidad=1)

        except StockInsuficienteError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # AUDITORÍA: registrar corrección con snapshot antes/después.
        # Fuera del atomic() para no anidar el log en la transacción de stock.
        administracion.refresh_from_db()
        self.audit_editar(request, antes, administracion)

        return Response(serializer.data)


# ── T-54, T-55 — Historial de administraciones ────────────


class AdministracionHistorialView(APIView):
    """
    GET /api/residentes/{id}/administraciones/  → historial con filtros (T-54, T-55)
    """

    permission_classes = [IsAdminOrCuidador]

    def get(self, request, pk):
        residente = get_object_or_404(Residente, pk=pk)

        queryset = AdministracionMedicamento.objects.filter(
            residente_medicamento__residente=residente
        ).select_related(
            "residente_medicamento__medicamento",
            "residente_medicamento__residente",
            "realizado_por",
        ).order_by("-id")  # Lo más reciente primero (recién registrado arriba)

        # Filtros opcionales
        fecha_desde = request.query_params.get("fecha_desde")
        fecha_hasta = request.query_params.get("fecha_hasta")
        administrado = request.query_params.get("administrado")

        if fecha_desde:
            queryset = queryset.filter(fecha_hora_programada__date__gte=fecha_desde)
        if fecha_hasta:
            queryset = queryset.filter(fecha_hora_programada__date__lte=fecha_hasta)
        if administrado is not None:
            valor = administrado.lower() == "true"
            queryset = queryset.filter(administrado=valor)

        # Paginación
        page = int(request.query_params.get("page", 1))
        page_size = 20
        start = (page - 1) * page_size
        end = start + page_size
        total = queryset.count()
        pagina = queryset[start:end]

        # T-55: resumen por período
        total_programadas = queryset.count()
        total_administradas = queryset.filter(administrado=True).count()
        total_omitidas = queryset.filter(administrado=False).count()

        serializer = AdministracionMedicamentoSerializer(pagina, many=True)
        return Response(
            {
                "total": total,
                "page": page,
                "pages": (total + page_size - 1) // page_size,
                "resumen": {
                    "total_programadas": total_programadas,
                    "total_administradas": total_administradas,
                    "total_omitidas": total_omitidas,
                },
                "results": serializer.data,
            }
        )
class MedicamentosResumenDashboardView(APIView):
    """
    GET /api/medicamentos/resumen-dashboard/
    Métricas + listas de medicamentos para el dashboard.
    """

    permission_classes = [IsAdminOrCuidador]

    def get(self, request):
        from django.utils import timezone
        hoy = timezone.now().date()

        # Catálogo activo (lista para el modal)
        medicamentos_activos_qs = CatalogoMedicamento.objects.filter(
            estado="activo"
        ).order_by("nombre_comercial")
        medicamentos_activos_lista = [
            {"id": m.id, "nombre": m.nombre_comercial, "forma": m.forma_farmaceutica}
            for m in medicamentos_activos_qs
        ]

        prescripciones_activas = ResidenteMedicamento.objects.filter(estado="activo").count()

        # Tomas de hoy
        tomas_hoy = AdministracionMedicamento.objects.filter(
            fecha_hora_programada__date=hoy
        ).select_related("residente_medicamento__medicamento", "residente_medicamento__residente")

        administradas_qs = tomas_hoy.filter(administrado=True)
        administradas_lista = [
            {
                "id": t.id,
                "medicamento": t.residente_medicamento.medicamento.nombre_comercial,
                "residente": f"{t.residente_medicamento.residente.nombre} {t.residente_medicamento.residente.apellido}",
                "hora": t.fecha_hora_programada.strftime("%H:%M"),
            }
            for t in administradas_qs
        ]
        administradas_hoy = administradas_qs.count()

        # Omitidas de hoy (con lista)
        omitidas_qs = tomas_hoy.filter(administrado=False)
        omitidas_lista = [
            {
                "id": t.id,
                "medicamento": t.residente_medicamento.medicamento.nombre_comercial,
                "residente": f"{t.residente_medicamento.residente.nombre} {t.residente_medicamento.residente.apellido}",
                "hora": t.fecha_hora_programada.strftime("%H:%M"),
            }
            for t in omitidas_qs
        ]
        omitidas_hoy = omitidas_qs.count()

        # Alertas de stock (reutiliza la función existente)
        alertas = get_alertas_stock()
        stock_bajo_lista = [
            {"medicamento": a["medicamento"], "lote": a["lote"], "cantidad": a["cantidad"], "umbral": a["umbral_minimo"]}
            for a in alertas if "stock_bajo" in a["tipos_alerta"]
        ]
        por_vencer_lista = [
            {"medicamento": a["medicamento"], "lote": a["lote"], "vence": str(a["fecha_vencimiento"])}
            for a in alertas if "vencimiento_proximo" in a["tipos_alerta"]
        ]

        # Total de lotes (para la dona: ok / bajo / por vencer)
        total_lotes = StockMedicamento.objects.count()
        lotes_bajo = len(stock_bajo_lista)
        lotes_por_vencer = len(por_vencer_lista)
        # "ok" = lotes que no están ni bajos ni por vencer (aprox: total menos alertados únicos)
        lotes_alertados = len({(a["medicamento"], a["lote"]) for a in alertas})
        lotes_ok = max(0, total_lotes - lotes_alertados)

        return Response({
            "medicamentos_activos": len(medicamentos_activos_lista),
            "medicamentos_activos_lista": medicamentos_activos_lista,
            "prescripciones_activas": prescripciones_activas,
            "administradas_hoy": administradas_hoy,
            "administradas_lista": administradas_lista,
            "omitidas_hoy": omitidas_hoy,
            "omitidas_lista": omitidas_lista,
            "stock_bajo": lotes_bajo,
            "stock_bajo_lista": stock_bajo_lista,
            "por_vencer": lotes_por_vencer,
            "por_vencer_lista": por_vencer_lista,
            "lotes_ok": lotes_ok,
            "total_lotes": total_lotes,
        })
