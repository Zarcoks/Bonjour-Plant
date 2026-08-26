import signal

from django.core.management.base import BaseCommand

from mqtt_worker import SensorListener


class Command(BaseCommand):
    help = "Listens to the installation on the MQTT broker. Runs until it is asked to stop."

    def leave(self, number, frame):
        raise KeyboardInterrupt

    def handle(self, *args, **options):
        # Docker stops a container with SIGTERM: taken as an interruption, so that
        # the listener disconnects and drops what it published about itself.
        signal.signal(signal.SIGTERM, self.leave)
        try:
            SensorListener().run()
        except KeyboardInterrupt:
            self.stdout.write("Écoute interrompue.")
