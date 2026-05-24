
SETTINGS_PROD = '''
from .settings import *
 
# Seguridad
DEBUG = False
ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=lambda v: [s.strip() for s in v.split(',')])
SECRET_KEY = config('SECRET_KEY')
 
# Base de datos (usar variables de entorno en producción)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME':     config('DB_NAME'),
        'USER':     config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST':     config('DB_HOST'),
        'PORT':     config('DB_PORT', default='5432'),
    }
}
 
# Archivos estáticos
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATIC_URL = '/static/'
 
# CORS — permitir el frontend
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    cast=lambda v: [s.strip() for s in v.split(',')],
    default='http://localhost:3000'
)
 
# Seguridad adicional
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
 
# Channel layers con Redis para producción
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [config('REDIS_URL', default='redis://localhost:6379')],
        },
    },
}
'''