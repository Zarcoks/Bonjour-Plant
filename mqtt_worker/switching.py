"""Making the plugs match the state the application says they should be in."""
import json

from django.conf import settings
from django.core.cache import cache
from paho.mqtt import publish as mqtt_publish

from core.app import app
from plant_management.models import STATE_OFF, STATE_ON, Actionner

from .broker import broker_from_url
from .listener import client_id

logger = app.module_logger("actionners")


# How long we remember what was last sent to a plug, so that the same order
# repeated every minute is not written in the journal every minute.
SENT_MEMORY_SECONDS = 24 * 3600


def state_of(actionner):
    return STATE_ON if actionner.is_on else STATE_OFF


def order_for(actionner):
    """
    The order to send this actionner: where to speak, and what to say.

    Its state goes out under the key it names its state with, which is the one
    it reports under too: a plug speaks the same way both ways round.
    """
    return {'topic': actionner.mqtt_topic_out,
            'payload': json.dumps({actionner.get_state_label(): state_of(actionner)})}


def to_be_told():
    """The actionners that can be reached at all."""
    return Actionner.objects.filter(is_deleted=False).exclude(mqtt_topic_out="")


def sent_key(actionner):
    return 'actionner:{}:sent'.format(actionner.pk)


def remember_what_was_sent(actionner):
    """
    Writes the order in the journal, unless it is the one already sent.

    The order goes out at every pass so that a plug switched by hand comes back
    in line, but only a change of instruction is worth a line: one line per plug
    per minute would bury every other record.
    """
    state = state_of(actionner)
    if cache.get(sent_key(actionner)) == state:
        return False
    cache.set(sent_key(actionner), state, timeout=SENT_MEMORY_SECONDS)
    logger.info("Instruction MQTT envoyée à l'actionneur " + actionner.name + " : "
                + state + " sur " + actionner.mqtt_topic_out)
    return True


def send_orders():
    """
    Tells every plug the state the application says it should be in.

    Sent again at every pass rather than only on a change: a plug switched by
    hand, or one that lost power and came back off, falls back in line on its
    own. Answers how many orders went out.
    """
    actionners = list(to_be_told())
    if not actionners:
        return 0

    broker = broker_from_url(settings.MQTT_BROKER_URL)
    mqtt_publish.multiple(
        [order_for(actionner) for actionner in actionners],
        hostname=broker.host,
        port=broker.port,
        client_id=client_id(),
        auth={'username': broker.username, 'password': broker.password} if broker.username else None,
        tls={} if broker.use_tls else None,
    )
    # Written down only once the broker took them.
    for actionner in actionners:
        remember_what_was_sent(actionner)
    return len(actionners)
