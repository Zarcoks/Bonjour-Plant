"""Turning the payload of a sensor into what it carries: measures, and charge."""
import json

from plant_management.models import LUMINOSITY_LEVELS

# The charges a battery can be reported at, in percent. Anything outside is not
# a charge: a sensor writing its voltage under that key is not at 3 %.
BATTERY_RANGE = (0, 100)


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


def as_object(payload):
    """The payload read as a JSON object, None when it is not one."""
    try:
        content = json.loads(payload)
    except (TypeError, ValueError):
        return None
    return content if isinstance(content, dict) else None


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
    content = as_object(payload)
    if content is None:
        return None

    found = {}
    for field, label, to_number in measures_of(sensor):
        if label not in content:
            continue
        value = to_number(content[label])
        if value is not None:
            found[field] = value
    return found


def read_battery(sensor, payload):
    """
    The charge a payload reports, in percent, read with the key of its sensor.

    Answers None when there is no charge to be read: a payload we cannot read, a
    sensor that says nothing of its batteries, or a figure off the percentage
    scale. Unlike the measures, this one is about the sensor itself and not
    about the plant it watches.
    """
    content = as_object(payload)
    if content is None:
        return None
    label = sensor.get_battery_label()
    if label not in content:
        return None
    level = to_int(content[label])
    if level is None or not BATTERY_RANGE[0] <= level <= BATTERY_RANGE[1]:
        return None
    return level
