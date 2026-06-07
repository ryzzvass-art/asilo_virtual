# medicamentos/stock_service.py
"""
Servicio de trazabilidad de stock.
Lógica FEFO (First Expired, First Out): se descuenta del lote que vence primero.
Todo movimiento queda registrado en MovimientoStock.
"""

from django.db import transaction
from django.utils import timezone
from .models import StockMedicamento, MovimientoStock


class StockInsuficienteError(Exception):
    """Se lanza cuando no hay ningún lote con unidades disponibles."""
    pass


@transaction.atomic
def descontar_por_administracion(administracion, usuario, cantidad=1):
    """
    Descuenta 'cantidad' unidades del stock del medicamento de esta administración,
    siguiendo FEFO (lote con menor fecha_vencimiento que tenga stock > 0).
    Registra un MovimientoStock de tipo 'salida' por cada lote tocado.

    Lanza StockInsuficienteError si no hay stock suficiente.
    Devuelve la lista de movimientos creados.
    """
    medicamento = administracion.residente_medicamento.medicamento

    # FEFO: lotes con stock disponible, ordenados por vencimiento más próximo.
    # select_for_update() bloquea las filas para evitar carreras si dos
    # cuidadores administran al mismo tiempo.
    lotes = (
        StockMedicamento.objects
        .select_for_update()
        .filter(medicamento=medicamento, cantidad__gt=0)
        .order_by("fecha_vencimiento", "id")
    )

    disponible_total = sum(lote.cantidad for lote in lotes)
    if disponible_total < cantidad:
        raise StockInsuficienteError(
            f"Stock insuficiente para '{medicamento.nombre_comercial}'. "
            f"Disponible: {disponible_total}, requerido: {cantidad}."
        )

    movimientos = []
    restante = cantidad

    for lote in lotes:
        if restante <= 0:
            break
        # Cuánto sacamos de este lote (no más de lo que tiene)
        sacar = min(lote.cantidad, restante)

        lote.cantidad -= sacar
        lote.actualizado_por = usuario
        lote.save(update_fields=["cantidad", "actualizado_por", "updated_at"])

        mov = MovimientoStock.objects.create(
            lote=lote,
            medicamento=medicamento,
            tipo=MovimientoStock.Tipo.SALIDA,
            cantidad=sacar,
            motivo="Administración de medicamento",
            administracion=administracion,
            realizado_por=usuario,
        )
        movimientos.append(mov)
        restante -= sacar

    return movimientos


@transaction.atomic
def revertir_administracion(administracion, usuario):
    """
    Devuelve al stock las unidades que se descontaron por esta administración.
    Busca los movimientos de 'salida' enlazados a la administración y crea
    movimientos de 'devolucion' que reponen al MISMO lote.

    Si un lote fue eliminado (lote=null), repone igual al medicamento creando
    el movimiento de devolución sin tocar un lote concreto (no hay dónde devolver).
    Devuelve la lista de movimientos de devolución creados.
    """
    salidas = MovimientoStock.objects.filter(
        administracion=administracion,
        tipo=MovimientoStock.Tipo.SALIDA,
    )

    devoluciones = []
    for salida in salidas:
        # Si el lote sigue existiendo, le devolvemos la cantidad.
        if salida.lote_id is not None:
            lote = StockMedicamento.objects.select_for_update().get(pk=salida.lote_id)
            lote.cantidad += salida.cantidad
            lote.actualizado_por = usuario
            lote.save(update_fields=["cantidad", "actualizado_por", "updated_at"])

        mov = MovimientoStock.objects.create(
            lote_id=salida.lote_id,  # mismo lote (o null si ya no existe)
            medicamento=salida.medicamento,
            tipo=MovimientoStock.Tipo.DEVOLUCION,
            cantidad=salida.cantidad,
            motivo="Reversión de administración corregida",
            administracion=administracion,
            realizado_por=usuario,
        )
        devoluciones.append(mov)

    return devoluciones