"""The Celery side of the battery worker."""
from celery import shared_task

from core.app import app

from . import checks

logger = app.module_logger("batteries")


@shared_task(name='battery_worker.check_the_batteries')
def check_the_batteries():
    """
    Looks at the batteries of every sensor, once an hour.

    Says nothing of itself: a sensor running low writes its own line, once, and
    stands on the main page until the user has changed its batteries and says so.
    """
    return checks.check_the_batteries()
