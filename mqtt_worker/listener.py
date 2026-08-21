"""The MQTT listener: what we subscribe to, and what we do with what arrives."""
import random
import string
import time

import paho.mqtt.client as mqtt
from django.conf import settings
from django.db import close_old_connections
from paho.mqtt.client import topic_matches_sub
from paho.mqtt.enums import CallbackAPIVersion

from core.app import app
from plant_management.models import Sensor, SensorData

from . import feedback, state, watering
from .broker import broker_from_url

logger = app.module_logger("mqtt")

# Two clients connected under the same name fight over the connection, so the
# name carries a random suffix.
CLIENT_ID_PREFIX = "bonjour-plant-"
CLIENT_ID_SUFFIX_LENGTH = 6

# How long a payload we keep, in characters.
MAX_PAYLOAD_LENGTH = 2000

# How long we wait before trying a broker that refused the connection again.
RECONNECT_SECONDS = 5


def client_id():
    return CLIENT_ID_PREFIX + "".join(random.choices(string.ascii_lowercase + string.digits,
                                                     k=CLIENT_ID_SUFFIX_LENGTH))


class SensorListener:
    """
    Listens to what the installation says, and records what arrives.

    Two kinds of topic are followed: the sensors, whose measures are kept, and
    the actionners that report their state, which is checked against what the
    application asked of them.

    The subscriptions are read from the database, and read again every
    `sync_seconds`: a device added, deleted or retopiced while the application
    runs is taken into account without a restart.
    """

    def __init__(self, broker=None, sync_seconds=None):
        self.broker = broker or broker_from_url(settings.MQTT_BROKER_URL)
        self.sync_seconds = sync_seconds or settings.MQTT_SYNC_SECONDS
        self.subscribed = set()
        self.running = False

    # ── What we listen to ─────────────────────────────────────

    def sensors(self):
        """Every sensor the application knows, assigned or not."""
        return Sensor.objects.filter(is_deleted=False).select_related('plant')

    def topics(self):
        """The topics to be subscribed to, as the database has them right now."""
        measures = {sensor.mqtt_topic for sensor in self.sensors() if sensor.mqtt_topic}
        return measures | feedback.topics()

    # ── What we do with what arrives ──────────────────────────

    def handle_message(self, topic, payload):
        """
        Records one measure per sensor listening on that topic, and returns them.

        A message on a topic no sensor claims any more is dropped, and so is a
        message from a sensor assigned to no plant. The same message is read for
        the actionners: a plug reporting a state it was not asked for is warned
        about, whether or not a sensor made anything of it.
        """
        # The connection of this thread may have been left open for a long time.
        close_old_connections()
        payload = payload[:MAX_PAYLOAD_LENGTH]
        feedback.check(topic, payload)
        recorded = []
        for sensor in self.sensors():
            if not sensor.mqtt_topic or not topic_matches_sub(sensor.mqtt_topic, topic):
                continue
            if sensor.plant_id is None:
                # logger.debug("Donnée ignorée sur " + topic + " : le capteur "
                #              + sensor.name + " n'est assigné à aucune plante")
                continue
            data = SensorData.objects.create(sensor=sensor, plant=sensor.plant, payload=payload)
            recorded.append(data)
            # A jump of humidity since a few minutes ago means somebody watered.
            watering.spot(sensor, data)
            # logger.debug("Donnée enregistrée sur " + topic + " pour " + sensor.plant.display_name)
        # if not recorded:
        #     logger.debug("Aucun capteur assigné n'écoute " + topic + " : donnée abandonnée")
        return recorded

    # ── Keeping the subscriptions in step with the database ───

    def sync_subscriptions(self, client):
        """Subscribes to what appeared, unsubscribes from what left."""
        close_old_connections()
        wanted = self.topics()
        for topic in sorted(wanted - self.subscribed):
            client.subscribe(topic)
            logger.info("Abonnement au topic " + topic)
        for topic in sorted(self.subscribed - wanted):
            client.unsubscribe(topic)
            logger.info("Désabonnement du topic " + topic)
        self.subscribed = wanted
        # Told to the rest of the application, which has no other way to know.
        state.publish(self.broker, self.subscribed)
        return self.subscribed

    # ── The connection ────────────────────────────────────────

    def build_client(self):
        client = mqtt.Client(client_id=client_id(), callback_api_version=CallbackAPIVersion.VERSION2)
        if self.broker.username:
            client.username_pw_set(self.broker.username, self.broker.password)
        if self.broker.use_tls:
            client.tls_set()
        client.on_connect = self.on_connect
        client.on_disconnect = self.on_disconnect
        client.on_message = self.on_message
        return client

    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code.is_failure:
            logger.error("Connexion au broker MQTT " + str(self.broker) + " refusée : " + str(reason_code))
            return
        logger.info("Connecté au broker MQTT " + str(self.broker))
        # A fresh connection carries no subscription: everything is taken again.
        self.subscribed = set()
        self.sync_subscriptions(client)

    def on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        logger.warning("Déconnecté du broker MQTT " + str(self.broker) + " : " + str(reason_code))
        self.subscribed = set()
        state.forget()

    def on_message(self, client, userdata, message, properties=None):
        try:
            self.handle_message(message.topic, message.payload.decode(errors='replace'))
        except Exception as error:
            # One bad message must not take the listener down.
            logger.error("Donnée MQTT non traitée sur " + message.topic + " : " + str(error))

    def run(self):
        """Connects, then keeps the subscriptions in step until interrupted."""
        client = self.build_client()
        client.reconnect_delay_set(min_delay=1, max_delay=RECONNECT_SECONDS)
        logger.info("Le worker MQTT démarre sur " + str(self.broker))
        client.connect(self.broker.host, self.broker.port)
        client.loop_start()
        self.running = True
        try:
            while self.running:
                time.sleep(self.sync_seconds)
                self.sync_subscriptions(client)
        finally:
            self.running = False
            client.loop_stop()
            client.disconnect()
            state.forget()
            logger.info("Le worker MQTT s'est arrêté")
