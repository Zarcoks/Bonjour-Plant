"""Checking that what a plug is asked to do shows up in the measures."""
import datetime

from django.utils import timezone

from mqtt_worker.feedback import KIND_EFFECT, warn
from plant_management.models import (ACT_ON_HUMIDITY, ACT_ON_LUMINOSITY, ACT_ON_TEMPERATURE,
                                     LUMINOSITY_LEVEL_NAMES, LUMINOSITY_LEVELS, Actionner,
                                     SensorData)
from sync_worker import read_measures

# Where the measure a plug acts on is written on a plant, and — for the measures
# judged on a rise — how it is named in a sentence, article included: the
# interface says "humidité", a warning says "l'humidité monte".
MEASURE_OF = {
    ACT_ON_HUMIDITY: 'current_humidity',
    ACT_ON_LUMINOSITY: 'current_luminosity',
    ACT_ON_TEMPERATURE: 'current_temperature',
}

# The level from which a lamp that is on shows in the measures. Light is not a
# quantity that climbs: it is there or it is not, and a plant already in full
# sun cannot go any higher — which is why a lamp is judged on the level reached
# and not on a rise. Deliberately stricter than WELL_LIT_INTENSITY, which only
# says whether a plant is in the light: here a lamp is on, so the level is
# expected to be high and not merely normal.
LAMP_SHOWS_AT = LUMINOSITY_LEVELS.index('high')

# A measure older than this says nothing about what a plug is doing right now:
# a sensor that stopped talking is not a plug that stopped working.
STALE_AFTER = datetime.timedelta(minutes=15)

# How many readings back we look for one that carries the measure. A plant may
# be watched by several sensors, and they do not all report everything.
READINGS_SCANNED = 20


def measure_in(data, field):
    """The measure that reading carries, read with the keys of its own sensor."""
    measures = read_measures(data.sensor, data.payload) or {}
    return measures.get(field)


def readings_of(plant, field, until=None):
    """
    The freshest reading of that measure on that plant, with its value.

    Looks a few readings back rather than at the last one only: the sensors of a
    plant do not all report the same measures. Answers (None, None) when none of
    them carries it.
    """
    readings = SensorData.objects.filter(plant=plant).select_related('sensor')
    if until is not None:
        readings = readings.filter(time__lte=until)
    for data in readings.order_by('-time')[:READINGS_SCANNED]:
        value = measure_in(data, field)
        if value is not None:
            return data, value
    return None, None


def how_it_reads(act_on, value):
    """A measure as the warning writes it."""
    if act_on == ACT_ON_LUMINOSITY:
        if 0 <= value < len(LUMINOSITY_LEVELS):
            return LUMINOSITY_LEVEL_NAMES[LUMINOSITY_LEVELS[value]]
        return str(value)
    return "{} {}".format(value, "%" if act_on == ACT_ON_HUMIDITY else "°C")


def light_drift(actionner, level):
    """
    What a lamp is belied by, in the level of light its plant receives.

    A lamp that is on and a plant that stays in the shade contradict each other,
    and so does a plant in full light with every lamp off. A level off the scale
    is no judgement at all.
    """
    if not 0 <= level < len(LUMINOSITY_LEVELS):
        return None
    reads = how_it_reads(ACT_ON_LUMINOSITY, level)
    if not actionner.is_on and level >= LAMP_SHOWS_AT:
        return "est éteint, mais la luminosité est " + reads
    if actionner.is_on and level < LAMP_SHOWS_AT:
        return "est allumé, mais la luminosité reste " + reads
    return None


def drift_of(actionner, now=None):
    """
    What a plug is belied by, in the measures of its plant, or None when nothing.

    A plug that is off while what it acts on climbs, and a plug that is on while
    it does not, are both belied — save for a lamp, judged on the level of light
    reached rather than on a rise. Anything in between is left alone, and so is a
    plug we cannot judge: no plant, no sensor reporting that measure, or nothing
    to compare the last reading with.
    """
    plant = actionner.plant
    field = MEASURE_OF.get(actionner.act_on)
    if plant is None or plant.is_deleted or field is None:
        return None

    now = now or timezone.now()
    latest, value = readings_of(plant, field)
    if latest is None or latest.time < now - STALE_AFTER:
        return None

    # A lamp is judged on the level reached, not on a rise: nothing to compare with.
    if actionner.act_on == ACT_ON_LUMINOSITY:
        return light_drift(actionner, value)

    return None


def check_the_actionners(now=None):
    """
    Warns about every plug the measures of its plant belie.

    Read-only on the plants: a plug that does nothing is the user's business,
    not something to switch around on our own. Answers how many were looked at
    and how many were found wanting.
    """
    summary = {'checked': 0, 'warned': 0}
    actionners = (Actionner.objects.filter(is_deleted=False)
                  .select_related('plant').exclude(plant=None))
    for actionner in actionners:
        summary['checked'] += 1
        drift = drift_of(actionner, now=now)
        if drift is None:
            continue
        warn(actionner, KIND_EFFECT, drift)
        summary['warned'] += 1
    return summary
