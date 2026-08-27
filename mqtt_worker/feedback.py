"""
What the devices of the installation say of themselves, and what we do when it
does not add up.

A plug belies us in two ways. It reports on its `mqtt_topic_in` a state it was
not asked for — read here, as the messages arrive. Or it takes its orders
without anything changing on the plant, which the coherence worker finds out
later, in the measures. A sensor says something of itself too: the charge of its
own batteries, which the battery worker looks at once an hour.

All of it leaves a warning in the cache, one entry per device and per kind, and
the main page shows them until the user says each one is settled: a plug that no
longer answers its orders, like a sensor running out of batteries, is not
something to notice once and forget.
"""
import json

from django.core.cache import cache
from django.utils import timezone
from paho.mqtt.client import topic_matches_sub

from core.app import app
from plant_management.models import STATE_OFF, STATE_ON, Actionner, Sensor

logger = app.module_logger("warnings")

# One entry per device and per kind, so that the pages can read them back
# without ever listing the cache: the devices of the database, crossed with the
# kinds below, are the index.
WARNING_KEY = '{}:{}:warning:{}'

# The devices that can be warned about, under the name their own model goes by.
SUBJECT_ACTIONNER = 'actionner'
SUBJECT_SENSOR = 'sensor'

# What each of them can be warned about. A plug can belie the application both
# ways at once, and each warning is raised, shown and settled on its own.
KIND_STATE = 'state'      # a plug says it is in a state it was not asked for
KIND_EFFECT = 'effect'    # what a plug acts on is not moving the way it should
KIND_BATTERY = 'battery'  # a sensor is running out of batteries

WARNING_KINDS = {
    SUBJECT_ACTIONNER: [KIND_STATE, KIND_EFFECT],
    SUBJECT_SENSOR: [KIND_BATTERY],
}

# Where the devices of a subject are read back from, and how each one is named
# in the journal, article included: "L'actionneur Lampe UV se dit allumé…".
SUBJECTS = {
    SUBJECT_ACTIONNER: {'model': Actionner, 'called': "L'actionneur"},
    SUBJECT_SENSOR: {'model': Sensor, 'called': "Le capteur"},
}

# What a plug may write to say it is on, and to say it is off, whatever its case.
ON_WORDS = {STATE_ON.lower(), 'on', 'true', 'yes', '1'}
OFF_WORDS = {STATE_OFF.lower(), 'off', 'false', 'no', '0'}


# ── Reading what a plug reports ───────────────────────────────

def to_state(value):
    """
    Whether that value means on or off, None when it means neither.

    Plugs say it in the words they like: "ON", "off", true, 1. Anything else is
    not a state, and a payload we cannot read is not a disagreement.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        value = int(value)
    word = str(value).strip().lower()
    if word in ON_WORDS:
        return True
    if word in OFF_WORDS:
        return False
    return None


def reported_state(actionner, payload):
    """
    The state a payload reports, read with the key of that actionner.

    Answers None when the payload is not a JSON object, does not carry the key,
    or carries something that is not a state.
    """
    try:
        content = json.loads(payload)
    except (TypeError, ValueError):
        return None
    if not isinstance(content, dict):
        return None
    label = actionner.get_state_label()
    if label not in content:
        return None
    return to_state(content[label])


# ── The warnings the user is shown ────────────────────────────

def subject_of(device):
    """
    The subject that device is warned about under.

    Read from the model itself — "actionner", "sensor" — so that raising a
    warning is done the same way whatever the device is.
    """
    return device._meta.model_name


def kinds_of(subject):
    """What that subject can be warned about, nothing when it is not a subject."""
    return WARNING_KINDS.get(subject, [])


def device_of(subject, device_id):
    """
    That device, as long as the application still knows it, else None.

    A subject we do not warn about, and a device deleted or gone, answer None
    the same way: there is nothing there to settle.
    """
    if subject not in SUBJECTS:
        return None
    return SUBJECTS[subject]['model'].objects.filter(pk=device_id, is_deleted=False).first()


def warning_key(subject, device_id, kind):
    return WARNING_KEY.format(subject, device_id, kind)


def warn(device, kind, message):
    """
    Leaves the warning where the pages can read it, and journals it once.

    `message` is the sentence that follows the name of the device, both on the
    page and in the journal. Kept without an expiry: only the user takes it
    away. A warning already standing is refreshed rather than raised again — one
    line in the journal per device that drifted, not one per pass that finds it
    still drifting.
    """
    subject = subject_of(device)
    key = warning_key(subject, device.pk, kind)
    already = cache.get(key)
    warning = {
        'subject': subject,
        'device': device.pk,
        'kind': kind,
        'name': device.name,
        'message': message,
        'since': already['since'] if already else timezone.now(),
        'at': timezone.now(),
    }
    cache.set(key, warning, timeout=None)
    if not already:
        logger.warning(SUBJECTS[subject]['called'] + " " + device.name + " " + message)
    return warning


def dismiss(device, kind=None):
    """
    Takes a warning away: the user says it is settled.

    Without a kind, every warning of that device goes — which is what deleting
    it means.
    """
    subject = subject_of(device)
    kinds = [kind] if kind else kinds_of(subject)
    cache.delete_many([warning_key(subject, device.pk, one) for one in kinds])


def standing():
    """
    Every warning standing, newest first.

    Read against the devices of the database rather than against the cache
    itself: a deleted plug, like a deleted sensor, stops being complained about
    on its own.
    """
    keys = [warning_key(subject, device.pk, kind)
            for subject, described in SUBJECTS.items()
            for device in described['model'].objects.filter(is_deleted=False)
            for kind in kinds_of(subject)]
    if not keys:
        return []
    return sorted(cache.get_many(keys).values(),
                  key=lambda warning: warning['at'], reverse=True)


# ── What the listener does with a message ─────────────────────

def listening_actionners():
    """The actionners that report on a topic of their own."""
    return Actionner.objects.filter(is_deleted=False).exclude(mqtt_topic_in="")


def topics():
    """The topics to be subscribed to for the actionners to be heard."""
    return {actionner.mqtt_topic_in for actionner in listening_actionners()}


def check(topic, payload):
    """
    Reads what arrived on that topic, and warns about every plug it belies.

    A plug reporting the state the application asked of it settles nothing on
    its own: the warning it may already have stands until the user says so.
    Answers the actionners that were found to disagree.
    """
    disagreeing = []
    for actionner in listening_actionners():
        if not topic_matches_sub(actionner.mqtt_topic_in, topic):
            continue
        reported = reported_state(actionner, payload)
        if reported is None or reported == actionner.is_on:
            continue
        warn(actionner, KIND_STATE, belies_message(reported, actionner.is_on))
        disagreeing.append(actionner)
    return disagreeing


def belies_message(reported, expected):
    """How a plug reporting the wrong state reads, after its name."""
    return ("se dit " + ("allumé" if reported else "éteint") + " alors que l'application le veut "
            + ("allumé" if expected else "éteint"))
