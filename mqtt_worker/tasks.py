"""The Celery side of the MQTT worker."""
from celery import shared_task
from celery.signals import worker_ready

from core.app import app

from . import state, switching
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
    # Ours from here on: kept alive at every synchronisation, and on every retry.
    state.keep_alive()
    try:
        SensorListener().run()
    except Exception as error:
        logger.error("L'écoute MQTT s'est interrompue : " + str(error))
        raise self.retry(exc=error, countdown=RETRY_SECONDS, max_retries=None)


@shared_task(name='mqtt_worker.switch_the_plugs')
def switch_the_plugs():
    """
    Brings the plugs in line with the application, on a schedule.

    A broker that cannot be reached is reported and nothing else: the next pass
    is a minute away, there is nothing to retry sooner.
    """
    try:
        return switching.send_orders()
    except Exception as error:
        logger.error("Les prises n'ont pas pu être commandées : " + str(error))
        return 0


@shared_task(name='mqtt_worker.watch_the_listening')
def watch_the_listening():
    """
    Starts the listening again when nobody holds it any more.

    `worker_ready` only fires when a worker starts, and the message was
    acknowledged the moment a child took it: a child killed mid-task takes the
    listening with it and nothing else would bring it back. Answers whether it
    had to start one.
    """
    if not state.claim():
        return False
    logger.warning("Personne n'écoute les capteurs : l'écoute est relancée")
    listen_to_sensors.apply_async()
    return True


@worker_ready.connect
def start_listening(sender=None, **kwargs):
    """Starts the listening as soon as a worker is up: nothing to launch by hand."""
    listen_to_sensors.apply_async()
