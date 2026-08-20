"""Spotting a watering in what a sensor reports."""
import datetime

from core.app import app
from plant_management.models import SensorData
from sync_worker import read_measures

logger = app.module_logger("watering")

# How far back we look for a humidity to compare with. A watering shows up
# between two measures at least this far apart, not between two consecutive ones.
LOOK_BACK = datetime.timedelta(minutes=3)

# How many points of humidity the rise has to be worth to count as a watering.
HUMIDITY_RISE = 15


def humidity_of(sensor, data):
    """The humidity a payload carries, read with the keys of its sensor."""
    measures = read_measures(sensor, data.payload) or {}
    return measures.get('current_humidity')


def measure_before(sensor, plant, data):
    """The last measure of that sensor, on that plant, taken LOOK_BACK before this one."""
    return (SensorData.objects.filter(sensor=sensor, plant=plant, time__lte=data.time - LOOK_BACK)
            .order_by('-time').first())


def spot(sensor, data):
    """
    Notes a watering on the plant when the humidity jumped since before.

    A rise, and not any change: humidity going down is the soil drying, which is
    the opposite of a watering. Answers whether a watering was noted.
    """
    plant = sensor.plant
    if plant is None:
        return False

    humidity = humidity_of(sensor, data)
    before = measure_before(sensor, plant, data)
    if humidity is None or before is None:
        return False

    humidity_before = humidity_of(sensor, before)
    if humidity_before is None or humidity - humidity_before <= HUMIDITY_RISE:
        return False

    plant.last_watering = data.time
    plant.save(update_fields=['last_watering'])
    logger.info("Arrosage détecté sur " + plant.display_name + " : humidité passée de "
                + str(humidity_before) + " % à " + str(humidity) + " %")
    return True
