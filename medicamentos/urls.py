

from django.urls import path
from .views import (
    MedicamentoListCreateView,
    MedicamentoDetailView,
    MedicamentoArchivarView,
    StockListCreateView,
    StockDetailView,
    AlertasStockView,
)

urlpatterns = [
    # ── Catálogo de medicamentos ────────────────────────────
    # GET  /api/medicamentos/              → listar (todos los roles)
    # POST /api/medicamentos/              → crear (solo Admin)
    path('medicamentos/', MedicamentoListCreateView.as_view(), name='medicamento-list-create'),

    # GET        /api/medicamentos/{id}/   → detalle
    # PATCH      /api/medicamentos/{id}/   → editar (solo Admin)
    path('medicamentos/<int:pk>/', MedicamentoDetailView.as_view(), name='medicamento-detail'),

    # PATCH /api/medicamentos/{id}/archivar/  → archivar (solo Admin)
    path('medicamentos/<int:pk>/archivar/', MedicamentoArchivarView.as_view(), name='medicamento-archivar'),

    # ── Stock por lote ──────────────────────────────────────
    # GET  /api/medicamentos/{id}/stock/           → listar lotes
    # POST /api/medicamentos/{id}/stock/           → agregar lote (solo Admin)
    path('medicamentos/<int:pk>/stock/', StockListCreateView.as_view(), name='stock-list-create'),

    # PATCH /api/medicamentos/{id}/stock/{lote_id}/  → actualizar lote (solo Admin)
    path('medicamentos/<int:pk>/stock/<int:lote_id>/', StockDetailView.as_view(), name='stock-detail'),

    # ── Alertas ─────────────────────────────────────────────
    # GET /api/alertas/stock/  → lotes con alertas activas
    path('alertas/stock/', AlertasStockView.as_view(), name='alertas-stock'),
]


# ============================================================
# GUÍA DE INTEGRACIÓN — SPRINT 4
# ============================================================

## PASO 1 — Copiar archivos a medicamentos/
##   models.py      → reemplaza el archivo vacío
##   apps.py        → reemplaza el existente
##   serializers.py → archivo NUEVO
##   views.py       → archivo NUEVO
##   urls.py        → archivo NUEVO (este mismo sin los comentarios de guía)

## PASO 2 — Registrar app en settings.py
## Abre asilo_virtual/settings.py y actualiza INSTALLED_APPS:
##
##   'medicamentos.apps.MedicamentosConfig',   # ← reemplaza 'medicamentos'

## PASO 3 — Registrar URLs en asilo_virtual/urls.py
##
##   path('api/', include('medicamentos.urls')),   # ← agregar esta línea

## PASO 4 — Migrar
##
##   python manage.py makemigrations medicamentos
##   python manage.py migrate

## PASO 5 — Pruebas Postman

## ✅ T-40 — Crear medicamento (solo Admin):
##   POST /api/medicamentos/
##   Body: {
##     "nombre_comercial": "Enalapril 10mg",
##     "principio_activo": "Enalapril maleato",
##     "tipo": "Antihipertensivo",
##     "forma_farmaceutica": "comprimido",
##     "contraindicaciones": "Hipersensibilidad al enalapril"
##   }
##   Con token cuidador → 403

## ✅ T-40 — Listar medicamentos:
##   GET /api/medicamentos/                          → solo activos
##   GET /api/medicamentos/?incluir_archivados=true  → todos
##   GET /api/medicamentos/?nombre=ena               → filtro por nombre

## ✅ T-41 — Archivar medicamento:
##   PATCH /api/medicamentos/1/archivar/
##   Luego GET /api/medicamentos/ → no debe aparecer
##   GET /api/medicamentos/?incluir_archivados=true → sí debe aparecer

## ✅ T-43, T-44 — Crear lote de stock:
##   POST /api/medicamentos/1/stock/
##   Body: {
##     "cantidad": 100,
##     "unidad": "comprimidos",
##     "fecha_vencimiento": "2027-06-30",
##     "umbral_minimo": 20,
##     "lote": "LOTE-2026-001"
##   }
##   Con fecha pasada → 400

## ✅ T-45 — Alertas de stock:
##   POST lote con cantidad=5 y umbral_minimo=20 (stock bajo)
##   POST lote con fecha_vencimiento=2026-05-10 (vence en <30 días)
##   GET /api/alertas/stock/ → debe mostrar ambos lotes con sus tipos de alerta
