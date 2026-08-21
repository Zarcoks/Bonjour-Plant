"""Checking that what a plug is asked to do shows up in the measures."""
import datetime

from django.utils import timezone

from mqtt_worker.feedback import KIND_EFFECT, warn
from plant_management.models import (ACT_ON_HUMIDITY, ACT_ON_LUMINOSITY, ACT_ON_TEMPERATURE,
                                     LUMINOSITY_LEVEL_NAMES, LUMINOSITY_LEVELS, Actionner,
                                     SensorData)
from sync_worker import read_measures

# Where the measure a plug acts on is written on a plant, and how it is named in
# a sentence, article included: the interface says "humidité", a warning says
# "l'humidité monte".
MEASURE_OF = {
    ACT_ON_HUMIDITY: 'current_humidity',
    ACT_ON_LUMINOSITY: 'current_luminosity',
    ACT_ON_TEMPERATURE: 'current_temperature',
}

MEASURE_NAMED = {
    ACT_ON_HUMIDITY: "l'humidité",
    ACT_ON_LUMINOSITY: "la lumière",
    ACT_ON_TEMPERATURE: "la température",
}

# How much the measure has to move up, while the plug is off, for the rise to be
# worth a warning. Under it the measure is only breathing: a room warms up on
# its own, and a soil does not dry at a constant rate.
SIGNIFICANT_RISE = {
    ACT_ON_HUMIDITY: 5,        # points of humidity
    ACT_ON_LUMINOSITY: 1,      # one step of the light scale
    ACT_ON_TEMPERATURE: 1.0,   # degrees
}

# How far back the comparison reaches. A pass covers the interval it runs on:
# the measure now, against the one taken before the plug had this long to act.
LOOK_BACK = datetime.timedelta(minutes=5)

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


def drift_of(actionner, now=None):
    """
    What a plug is belied by, in the measures of its plant, or None when nothing.

    A plug that is off while what it acts on climbs, and a plug that is on while
    it does not, are both belied. Anything in between is left alone, and so is a
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
    earlier, before = readings_of(plant, field, until=latest.time - LOOK_BACK)
    if earlier is None:
        return None

    moved = value - before
    reads = how_it_reads(actionner.act_on, before) + " puis " + how_it_reads(actionner.act_on, value)
    measure = MEASURE_NAMED[actionner.act_on]
    if not actionner.is_on and moved >= SIGNIFICANT_RISE[actionner.act_on]:
        return "est éteint, mais " + measure + " monte quand même (" + reads + ")"
    if actionner.is_on and moved <= 0:
        return "est allumé, mais " + measure + " ne monte pas (" + reads + ")"
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
