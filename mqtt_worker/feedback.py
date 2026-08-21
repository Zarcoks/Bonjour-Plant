"""
What the plugs say of themselves, and what we do when it does not match.

An actionner that reports on its `mqtt_topic_in` is telling us whether it is
really on or off. When that disagrees with what the application asked of it,
somebody has to know: the disagreement is left in the cache, the main page shows
it, and it stays there until the user says it is settled — a plug that no longer
answers its orders is not something to notice once and forget.
"""
import json

from django.core.cache import cache
from django.utils import timezone
from paho.mqtt.client import topic_matches_sub

from core.app import app
from plant_management.models import STATE_OFF, STATE_ON, Actionner

logger = app.module_logger("actionners")

# One entry per actionner, so that the pages can read them back without ever
# listing the cache: the actionners of the database are the index.
WARNING_KEY = 'actionner:{}:disagreement'

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


# ── The disagreements the user is shown ───────────────────────

def warning_key(actionner_id):
    return WARNING_KEY.format(actionner_id)


def warn(actionner, reported):
    """
    Leaves the disagreement where the pages can read it, and journals it once.

    Kept without an expiry: only the user takes it away. A disagreement already
    standing is refreshed rather than raised again — one line in the journal per
    plug that drifted, not one per message it sends.
    """
    key = warning_key(actionner.pk)
    standing = cache.get(key)
    warning = {
        'actionner': actionner.pk,
        'name': actionner.name,
        'expected': actionner.is_on,
        'reported': reported,
        'since': standing['since'] if standing else timezone.now(),
        'at': timezone.now(),
    }
    cache.set(key, warning, timeout=None)
    if not standing:
        logger.warning("L'actionneur " + actionner.name + " se dit "
                       + ("allumé" if reported else "éteint") + " alors qu'il est "
                       + ("allumé" if actionner.is_on else "éteint") + " pour l'application")
    return warning


def dismiss(actionner_id):
    """Takes a disagreement away: the user says it is settled."""
    cache.delete(warning_key(actionner_id))


def disagreements():
    """
    Every disagreement standing, newest first.

    Read against the actionners of the database rather than against the cache
    itself: a deleted actionner stops being complained about on its own.
    """
    actionners = Actionner.objects.filter(is_deleted=False)
    keys = {warning_key(actionner.pk): actionner for actionner in actionners}
    if not keys:
        return []
    standing = cache.get_many(list(keys))
    return sorted(standing.values(), key=lambda warning: warning['at'], reverse=True)


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
        warn(actionner, reported)
        disagreeing.append(actionner)
    return disagreeing
