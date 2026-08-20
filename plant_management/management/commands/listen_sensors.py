from django.core.management.base import BaseCommand

from mqtt_worker import SensorListener


class Command(BaseCommand):
    help = "Listens to the sensors on the MQTT broker, without going through Celery."

    def handle(self, *args, **options):
        try:
            SensorListener().run()
        except KeyboardInterrupt:
            self.stdout.write("Écoute interrompue.")
