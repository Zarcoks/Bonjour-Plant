"""The Celery side of the coherence worker."""
from celery import shared_task

from core.app import app

from .checks import check_the_actionners

logger = app.module_logger("coherence")


@shared_task(name='coherence_worker.check_the_plugs')
def check_the_plugs():
    """
    Looks at every plug against the measures of its plant.

    Says nothing of itself: a plug found wanting writes its own line, once,
    and stands on the main page until the user settles it.
    """
    return check_the_actionners()
