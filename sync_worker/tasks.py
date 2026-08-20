"""The Celery side of the synchronisation worker."""
from celery import shared_task

from core.app import app

from .sync import sync_plants

logger = app.module_logger("sync")


@shared_task(name='sync_worker.sync_sensors_to_plants')
def sync_sensors_to_plants():
    """
    Writes the last measures received on the plants that are watched.

    Runs on a schedule, and says nothing when nothing moved: the journal keeps
    the runs that changed something.
    """
    summary = sync_plants()
    # if summary['plants']:
    #     logger.info("Mesures synchronisées : " + str(summary['measures']) + " sur "
    #                 + str(summary['plants']) + " plante(s)")
    if summary['unreadable']:
        logger.warning(str(summary['unreadable']) + " payload(s) de capteur illisible(s), ignoré(s)")
    return summary
