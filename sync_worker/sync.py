"""Writing the freshest measures of the sensors on the plants."""
from plant_management.models import GrowingPlant

from .measures import read_measures


def freshest_measures(plant):
    """
    The most recent value of each measure among the sensors of this plant.

    Returns the measures, and how many payloads could not be read: a plant may
    be watched by several sensors, and the latest one to speak wins.
    """
    freshest = {}
    unreadable = 0
    for sensor in plant.sensors.filter(is_deleted=False):
        data = sensor.data.order_by('-time').first()
        if data is None:
            continue
        measures = read_measures(sensor, data.payload)
        if measures is None:
            unreadable += 1
            continue
        for field, value in measures.items():
            if field not in freshest or data.time > freshest[field][0]:
                freshest[field] = (data.time, value)
    return {field: value for field, (moment, value) in freshest.items()}, unreadable


def sync_plants():
    """
    Copies the measures of the sensors onto the plants, and says what it did.

    A plant whose measures have not moved is left alone, and only the fields
    that changed are written.
    """
    summary = {'plants': 0, 'measures': 0, 'unreadable': 0}
    for plant in GrowingPlant.objects.filter(is_deleted=False):
        measures, unreadable = freshest_measures(plant)
        summary['unreadable'] += unreadable
        changed = [field for field, value in measures.items() if getattr(plant, field) != value]
        if not changed:
            continue
        for field in changed:
            setattr(plant, field, measures[field])
        plant.save(update_fields=changed)
        summary['plants'] += 1
        summary['measures'] += len(changed)
    return summary
