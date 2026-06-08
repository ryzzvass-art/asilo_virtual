#!/usr/bin/env bash

echo "🚀 Iniciando Asilo Virtual en Render..."

# Esperar que PostgreSQL esté completamente listo
echo "⏳ Esperando a PostgreSQL (puede tardar unos segundos)..."
sleep 10

# Reintento de migraciones con espera
echo "📦 Aplicando migraciones..."
until python manage.py migrate --noinput; do
    echo "⚠️  Base de datos aún no lista, reintentando en 3 segundos..."
    sleep 3
done

echo "👤 Creando/actualizando admin..."
python manage.py crear_admin || echo "⚠️  Comando crear_admin falló (puede no ser crítico)"

echo "✅ Todo listo. Iniciando servidor ASGI (Daphne)..."
exec daphne -b 0.0.0.0 -p $PORT asilo_virtual.asgi:application