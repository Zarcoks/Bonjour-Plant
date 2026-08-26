"""The Celery side of the MQTT worker."""
from celery import shared_task

from core.app import app

from . import switching

logger = app.module_logger("mqtt")


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
