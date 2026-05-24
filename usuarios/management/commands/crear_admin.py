from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

Usuario = get_user_model()

class Command(BaseCommand):
    help = 'Crea el usuario administrador inicial'

    def handle(self, *args, **options):
        if not Usuario.objects.filter(email='admin@asilo.com').exists():
            Usuario.objects.create_user(
                email='admin@asilo.com',
                nombre='Administrador',
                apellido='Sistema',
                rol='administrador',
                password='Admin1234!',
            )
            self.stdout.write(self.style.SUCCESS('✅ Admin creado: admin@asilo.com / Admin1234!'))
        else:
            self.stdout.write('⚠️ El admin ya existe')