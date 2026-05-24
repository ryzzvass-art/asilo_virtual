README = '''
# Sistema de Gestión — Asilo Virtual
 
API REST para gestión integral de un asilo de ancianos.
Django 6 + PostgreSQL + JWT + Django Channels
 
## Requisitos
 
- Python 3.12+
- PostgreSQL 16
- Redis (para WebSocket en producción)
 
## Instalación
 
```bash
# Clonar repositorio
git clone <repo_url>
cd asilo_virtual
 
# Crear entorno virtual
python -m venv venv
venv\\Scripts\\activate  # Windows
source venv/bin/activate  # Linux/Mac
 
# Instalar dependencias
pip install -r requirements.txt
 
# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus valores
 
# Migrar base de datos
python manage.py migrate
 
# Crear superusuario
python manage.py createsuperuser
 
# Ejecutar servidor
python manage.py runserver
```
 
## Variables de entorno (.env)
 
```
SECRET_KEY=tu-clave-secreta
DEBUG=True
DB_NAME=asilo_db
DB_USER=postgres
DB_PASSWORD=tu_password
DB_HOST=localhost
DB_PORT=5432
EMAIL_HOST_USER=tucorreo@gmail.com
EMAIL_HOST_PASSWORD=tu_app_password
DEFAULT_FROM_EMAIL=tucorreo@gmail.com
```
 
## Documentación de la API
 
Con el servidor corriendo:
- Swagger UI: http://localhost:8000/api/schema/swagger-ui/
- ReDoc:       http://localhost:8000/api/schema/redoc/
 
## Ejecutar tests
 
```bash
pytest
pytest -v                    # verbose
pytest usuarios/tests.py     # solo un módulo
pytest --tb=short            # errores resumidos
```
 
## Estructura del proyecto
 
```
asilo_virtual/    ← Configuración principal
usuarios/         ← Autenticación JWT, roles
residentes/       ← Residentes, historial, observaciones, turnos
medicamentos/     ← Catálogo, stock, prescripciones, tomas, WebSocket
nutricion/        ← Restricciones, alimentos, planes nutricionales
actividades/      ← Actividades y eventos
visitas/          ← Visitantes y registros de visita
auditoria/        ← Audit log y dashboard
```
 
## Stack tecnológico
 
- **Backend**: Django 6, Django REST Framework
- **Base de datos**: PostgreSQL 16
- **Autenticación**: JWT (SimpleJWT)
- **WebSocket**: Django Channels + Daphne
- **Documentación**: drf-spectacular (OpenAPI 3.0)
- **Tests**: pytest-django
'''
 
# Guardar README
with open('/mnt/user-data/outputs/sprint10/README.md', 'w', encoding='utf-8') as f:
    f.write(README.strip())
 
print("README generado")
 