"""The Celery side of the decision worker."""
from celery import shared_task

from core.app import app

from .light import light_the_plants
from .watering import water_the_plants

logger = app.module_logger("decisions")


@shared_task(name='decision_worker.take_the_decisions')
def take_the_decisions():
    """
    Runs every decision the application takes on its own, and answers what each
    of them switched.

    Says nothing when it changed nothing: a decision worth knowing about is one
    that switched something, and each switch writes its own line.
    """
    return {'light': light_the_plants(), 'watering': water_the_plants()}
