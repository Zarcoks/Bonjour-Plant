"""Turning the payload of a sensor into measures a plant can hold."""
import json

from plant_management.models import LUMINOSITY_LEVELS


def to_int(value):
    """A whole number, or None when the value is not one."""
    try:
        return round(float(value))
    except (TypeError, ValueError):
        return None


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_level(value):
    """
    The rank of a light level, from the name the sensor gives it.

    Sensors report the light as one of "low-", "low", "nor", "high" and "high+"
    rather than as a number. A rank already on the scale is taken as it is;
    anything else is not a level.
    """
    if isinstance(value, str):
        name = value.strip().lower()
        return LUMINOSITY_LEVELS.index(name) if name in LUMINOSITY_LEVELS else None
    rank = to_int(value)
    if rank is not None and 0 <= rank < len(LUMINOSITY_LEVELS):
        return rank
    return None


def measures_of(sensor):
    """
    What to read in this sensor's payload, and where it lands on the plant.

    The keys come from the sensor itself: two sensors rarely name their measures
    the same way.
    """
    return [
        ('current_humidity', sensor.get_humidity_label(), to_int),
        ('current_luminosity', sensor.get_luminosity_label(), to_level),
        ('current_temperature', sensor.get_temperature_label(), to_float),
    ]


def read_measures(sensor, payload):
    """
    The measures a payload carries, ready to be written on a plant.

    Answers None when the payload is not a JSON object at all. A key the payload
    does not carry, or carries without a number, is simply left out.
    """
    try:
        content = json.loads(payload)
    except (TypeError, ValueError):
        return None
    if not isinstance(content, dict):
        return None

    found = {}
    for field, label, to_number in measures_of(sensor):
        if label not in content:
            continue
        value = to_number(content[label])
        if value is not None:
            found[field] = value
    return found
