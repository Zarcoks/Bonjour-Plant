"""The Celery side of the MQTT worker."""
from celery import shared_task
from celery.signals import worker_ready

from core.app import app

from .listener import SensorListener

logger = app.module_logger("mqtt")

# How long we wait before listening again after the listener fell over.
RETRY_SECONDS = 10


@shared_task(bind=True, name='mqtt_worker.listen_to_sensors')
def listen_to_sensors(self):
    """
    Listens to the sensors, forever.

    The task holds the connection for as long as the worker lives; should it
    fall over, it is queued again rather than left dead.
    """
    try:
        SensorListener().run()
    except Exception as error:
        logger.error("L'écoute MQTT s'est interrompue : " + str(error))
        raise self.retry(exc=error, countdown=RETRY_SECONDS, max_retries=None)


@worker_ready.connect
def start_listening(sender=None, **kwargs):
    """Starts the listening as soon as a worker is up: nothing to launch by hand."""
    listen_to_sensors.apply_async()
