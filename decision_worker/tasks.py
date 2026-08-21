"""The Celery side of the decision worker."""
from celery import shared_task

from core.app import app

from .light import light_the_plants

logger = app.module_logger("decisions")


@shared_task(name='decision_worker.take_the_decisions')
def take_the_decisions():
    """
    Runs every decision the application takes on its own.

    Says nothing when it changed nothing: a decision worth knowing about is one
    that switched something, and each switch writes its own line.
    """
    return light_the_plants()
