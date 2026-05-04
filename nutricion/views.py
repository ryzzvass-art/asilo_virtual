
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models import (
    CatalogoRestriccion, CatalogoAlimento,
    AlimentoRestriccion, ResidenteRestriccion
)
from .serializers import (
    CatalogoRestriccionSerializer,
    CatalogoAlimentoSerializer,
    AlimentoRestriccionSerializer,
    ResidenteRestriccionSerializer,
    AsignarRestriccionSerializer,
)
from usuarios.permissions import IsAdministrador, IsAdminOrCuidador
from residentes.models import Residente


# ── T-59, T-60 — Catálogo de Restricciones ────────────────

class RestriccionListCreateView(APIView):
    """
    GET  /api/restricciones/  → listar activas (todos los roles)
    POST /api/restricciones/  → crear (solo Admin)
    """

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdministrador()]
        return [IsAdminOrCuidador()]

    def get(self, request):
        incluir = request.query_params.get('incluir_archivadas', 'false')
        if incluir.lower() == 'true':
            queryset = CatalogoRestriccion.objects.all()
        else:
            queryset = CatalogoRestriccion.objects.filter(estado='activo')
        serializer = CatalogoRestriccionSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = CatalogoRestriccionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save(creado_por=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class RestriccionDetailView(APIView):
    """
    GET   /api/restricciones/{id}/  → detalle
    PATCH /api/restricciones/{id}/  → editar (solo Admin)
    """

    def get_permissions(self):
        if self.request.method == 'PATCH':
            return [IsAdministrador()]
        return [IsAdminOrCuidador()]

    def get(self, request, pk):
        restriccion = get_object_or_404(CatalogoRestriccion, pk=pk)
        return Response(CatalogoRestriccionSerializer(restriccion).data)

    def patch(self, request, pk):
        restriccion = get_object_or_404(CatalogoRestriccion, pk=pk)
        serializer  = CatalogoRestriccionSerializer(
            restriccion, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)


class RestriccionArchivarView(APIView):
    """PATCH /api/restricciones/{id}/archivar/ → archivar (solo Admin)"""
    permission_classes = [IsAdministrador]

    def patch(self, request, pk):
        restriccion = get_object_or_404(CatalogoRestriccion, pk=pk)
        if restriccion.estado == 'archivado':
            return Response(
                {"error": "Esta restricción ya está archivada."},
                status=status.HTTP_400_BAD_REQUEST
            )
        restriccion.estado = 'archivado'
        restriccion.save(update_fields=['estado'])
        return Response({
            "mensaje": f"Restricción '{restriccion.nombre}' archivada.",
            "estado":  restriccion.estado,
        })


# ── T-61, T-62 — Catálogo de Alimentos ────────────────────

class AlimentoListCreateView(APIView):
    """
    GET  /api/alimentos/  → listar activos (todos los roles)
    POST /api/alimentos/  → crear con estado='pendiente'
    """

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdministrador()]
        return [IsAdminOrCuidador()]

    def get(self, request):
        incluir = request.query_params.get('incluir_no_activos', 'false')
        if incluir.lower() == 'true':
            queryset = CatalogoAlimento.objects.all()
        else:
            queryset = CatalogoAlimento.objects.filter(estado='activo')

        nombre = request.query_params.get('nombre')
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
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AlimentoActivarView(APIView):
    """
    PATCH /api/alimentos/{id}/activar/
    T-62: Solo Admin puede activar. Registra revisado_por.
    """
    permission_classes = [IsAdministrador]

    def patch(self, request, pk):
        alimento = get_object_or_404(CatalogoAlimento, pk=pk)
        if alimento.estado == 'activo':
            return Response(
                {"error": "Este alimento ya está activo."},
                status=status.HTTP_400_BAD_REQUEST
            )
        alimento.estado      = 'activo'
        alimento.revisado_por = request.user
        alimento.save(update_fields=['estado', 'revisado_por'])
        return Response({
            "mensaje":     f"Alimento '{alimento.nombre}' activado.",
            "estado":      alimento.estado,
            "revisado_por": f"{request.user.nombre} {request.user.apellido}",
        })


class AlimentoDetailView(APIView):
    """
    GET   /api/alimentos/{id}/  → detalle con restricciones que viola
    PATCH /api/alimentos/{id}/  → editar (solo Admin)
    """

    def get_permissions(self):
        if self.request.method == 'PATCH':
            return [IsAdministrador()]
        return [IsAdminOrCuidador()]

    def get(self, request, pk):
        alimento   = get_object_or_404(CatalogoAlimento, pk=pk)
        serializer = CatalogoAlimentoSerializer(alimento)
        return Response(serializer.data)

    def patch(self, request, pk):
        alimento   = get_object_or_404(CatalogoAlimento, pk=pk)
        serializer = CatalogoAlimentoSerializer(
            alimento, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)


# ── T-63, T-64 — Vinculación Alimento-Restricción ─────────

class AlimentoRestriccionView(APIView):
    """
    GET    /api/alimentos/{id}/restricciones/              → listar restricciones del alimento
    POST   /api/alimentos/{id}/restricciones/              → vincular restricción
    DELETE /api/alimentos/{id}/restricciones/{rid}/        → desvincular
    """
    permission_classes = [IsAdministrador]

    def get(self, request, pk):
        alimento = get_object_or_404(CatalogoAlimento, pk=pk)
        vínculos = AlimentoRestriccion.objects.filter(
            alimento=alimento
        ).select_related('restriccion')
        serializer = AlimentoRestriccionSerializer(vínculos, many=True)
        return Response(serializer.data)

    def post(self, request, pk):
        """T-64: Vincular restricción a alimento."""
        alimento = get_object_or_404(CatalogoAlimento, pk=pk)

        restriccion_id = request.data.get('restriccion_id')
        if not restriccion_id:
            return Response(
                {"error": "restriccion_id es requerido."},
                status=status.HTTP_400_BAD_REQUEST
            )

        restriccion = get_object_or_404(CatalogoRestriccion, pk=restriccion_id)

        # Verificar que no exista ya el vínculo
        if AlimentoRestriccion.objects.filter(
            alimento=alimento, restriccion=restriccion
        ).exists():
            return Response(
                {"error": "Esta restricción ya está vinculada a este alimento."},
                status=status.HTTP_400_BAD_REQUEST
            )

        vinculo    = AlimentoRestriccion.objects.create(
            alimento=alimento, restriccion=restriccion
        )
        serializer = AlimentoRestriccionSerializer(vinculo)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request, pk, rid):
        alimento    = get_object_or_404(CatalogoAlimento, pk=pk)
        restriccion = get_object_or_404(CatalogoRestriccion, pk=rid)
        vinculo     = get_object_or_404(
            AlimentoRestriccion, alimento=alimento, restriccion=restriccion
        )
        vinculo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── T-65, T-66, T-67 — Restricciones del Residente ────────

class ResidenteRestriccionView(APIView):
    """
    GET  /api/residentes/{id}/restricciones/  → listar restricciones activas
    POST /api/residentes/{id}/restricciones/  → asignar con confirmación (RF-22-C)
    """
    permission_classes = [IsAdminOrCuidador]

    def get(self, request, pk):
        residente = get_object_or_404(Residente, pk=pk)
        queryset  = ResidenteRestriccion.objects.filter(
            residente=residente, estado='activa'
        ).select_related('restriccion', 'confirmado_por')
        serializer = ResidenteRestriccionSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request, pk):
        """
        T-66: Sugiere restricciones según condiciones_cronicas del residente.
        T-67: restricción obligatoria requiere confirmado=True.
        """
        residente  = get_object_or_404(Residente, pk=pk)
        serializer = AsignarRestriccionSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        restriccion = serializer.validated_data['restriccion']

        # Verificar que no esté ya activa
        if ResidenteRestriccion.objects.filter(
            residente=residente,
            restriccion=restriccion,
            estado='activa'
        ).exists():
            return Response(
                {"error": f"La restricción '{restriccion.nombre}' ya está activa para este residente."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Crear la restricción confirmada
        rr = ResidenteRestriccion.objects.create(
            residente=residente,
            restriccion=restriccion,
            confirmado_por=request.user,
        )

        # T-66: sugerir otras restricciones basadas en condiciones_cronicas
        sugeridas = []
        try:
            condiciones = residente.historial_medico.condiciones_cronicas.lower()
            if condiciones:
                otras = CatalogoRestriccion.objects.filter(
                    estado='activo'
                ).exclude(pk=restriccion.pk)

                for r in otras:
                    palabras = [
                        p.strip() for p in r.condiciones_asociadas.lower().split(',')
                        if len(p.strip()) > 3
                    ]
                    if any(p in condiciones for p in palabras):
                        # Solo sugerir si no está ya activa
                        ya_activa = ResidenteRestriccion.objects.filter(
                            residente=residente,
                            restriccion=r,
                            estado='activa'
                        ).exists()
                        if not ya_activa:
                            sugeridas.append({
                                'id':       r.pk,
                                'nombre':   r.nombre,
                                'severidad': r.severidad,
                            })
        except Exception:
            pass

        response_data = ResidenteRestriccionSerializer(rr).data
        if sugeridas:
            response_data = dict(response_data)
            response_data['sugeridas'] = sugeridas

        return Response(response_data, status=status.HTTP_201_CREATED)


class ResidenteRestriccionRevocarView(APIView):
    """PATCH /api/residentes/{id}/restricciones/{rr_id}/revocar/"""
    permission_classes = [IsAdminOrCuidador]

    def patch(self, request, pk, rr_id):
        residente = get_object_or_404(Residente, pk=pk)
        rr        = get_object_or_404(
            ResidenteRestriccion, pk=rr_id, residente=residente
        )
        if rr.estado == 'revocada':
            return Response(
                {"error": "Esta restricción ya está revocada."},
                status=status.HTTP_400_BAD_REQUEST
            )
        rr.estado = 'revocada'
        rr.save(update_fields=['estado'])
        return Response({
            "mensaje": f"Restricción '{rr.restriccion.nombre}' revocada.",
            "estado":  rr.estado,
        })
