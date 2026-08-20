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


def growing_state_moved(plant):
    """
    Sets how far along the plant should be, and answers whether that moved.

    Unlike the measures, this one owes nothing to the sensors: it follows the
    calendar, so it is worked out at every pass. A harvested plant keeps the
    progression it had — its growing is over, and counting on would carry it
    past its own harvest.
    """
    if plant.harvested:
        return False
    expected = plant.expected_growing_state()
    if expected is None or plant.growing_state == expected:
        return False
    plant.growing_state = expected
    return True


def sync_plants():
    """
    Copies the measures of the sensors onto the plants, brings their progression
    up to date, and says what it did.

    A plant with nothing to change is left alone, and only the fields that
    changed are written — in a single write.
    """
    summary = {'plants': 0, 'measures': 0, 'unreadable': 0, 'grown': 0}
    for plant in GrowingPlant.objects.filter(is_deleted=False):
        measures, unreadable = freshest_measures(plant)
        summary['unreadable'] += unreadable

        changed = [field for field, value in measures.items() if getattr(plant, field) != value]
        for field in changed:
            setattr(plant, field, measures[field])
        grown = growing_state_moved(plant)

        if not changed and not grown:
            continue
        plant.save(update_fields=changed + (['growing_state'] if grown else []))
        summary['plants'] += 1
        summary['measures'] += len(changed)
        summary['grown'] += 1 if grown else 0
    return summary
