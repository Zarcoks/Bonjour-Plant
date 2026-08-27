"""Checking that the sensors still have the batteries to keep talking."""
from mqtt_worker.feedback import KIND_BATTERY, warn
from plant_management.models import Sensor


def low_battery_message(level):
    """How a sensor running out of batteries reads, after its name."""
    return ("n'a plus que " + str(level) + " % de batterie : il est temps de changer ses piles")


def check_the_batteries():
    """
    Warns about every sensor whose batteries are worth changing.

    Read from the charge each sensor last reported of itself, which the MQTT
    worker writes as the messages arrive: a sensor that has never said anything
    of its batteries is not judged — silence is not an empty battery. Read-only
    on the sensors: changing batteries is the user's business, and the warning
    stands until they say it is done.

    Answers how many sensors were looked at and how many were found low.
    """
    summary = {'checked': 0, 'warned': 0}
    for sensor in Sensor.objects.filter(is_deleted=False).exclude(battery_level=None):
        summary['checked'] += 1
        if not sensor.battery_is_low():
            continue
        warn(sensor, KIND_BATTERY, low_battery_message(sensor.battery_level))
        summary['warned'] += 1
    return summary
