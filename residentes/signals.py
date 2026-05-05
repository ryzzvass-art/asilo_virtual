from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Residente, HistorialMedico


@receiver(post_save, sender=Residente)
def crear_historial_medico(sender, instance, created, **kwargs):
    """
    Se ejecuta automáticamente cada vez que se guarda un Residente.

    - sender:   el modelo que disparó el signal (Residente)
    - instance: el objeto Residente que se acaba de guardar
    - created:  True si es un registro NUEVO, False si es una edición
    """
    if created:
        # Solo crea el historial cuando el residente es NUEVO
        # Si es una edición (created=False), no hace nada
        HistorialMedico.objects.create(residente=instance)
