"""The MQTT worker: what it subscribes to, and what it does with what arrives."""
import pytest

from mqtt_worker import SensorListener, broker_from_url
from mqtt_worker.listener import MAX_PAYLOAD_LENGTH, client_id
from plant_management.models import Sensor, SensorData


@pytest.fixture
def listener():
    return SensorListener(broker=broker_from_url("mqtt://broker:1883"), sync_seconds=1)


# --- Where the broker is ---

def test_a_plain_broker_url_is_read():
    broker = broker_from_url("mqtt://broker.local:1883")
    assert (broker.host, broker.port) == ("broker.local", 1883)
    assert not broker.use_tls
    assert broker.username is None


def test_the_port_falls_back_on_the_scheme():
    assert broker_from_url("mqtt://broker.local").port == 1883
    assert broker_from_url("mqtts://broker.local").port == 8883


def test_an_encrypted_url_carries_its_credentials():
    broker = broker_from_url("mqtts://sonde:secret@broker.local:8884")
    assert (broker.host, broker.port) == ("broker.local", 8884)
    assert (broker.username, broker.password) == ("sonde", "secret")
    assert broker.use_tls


def test_a_url_without_a_scheme_is_understood():
    assert broker_from_url("broker.local:1883").host == "broker.local"


def test_a_url_without_a_host_is_refused():
    with pytest.raises(ValueError):
        broker_from_url("mqtt://")


def test_two_clients_do_not_share_a_name():
    assert client_id() != client_id()


# --- What we subscribe to ---

def test_the_topics_come_from_the_sensors(listener, sensor, growing_plant):
    assert listener.topics() == {"bonjour-plant/balcon/humidity"}


def test_a_sensor_assigned_to_nothing_is_listened_to_all_the_same(listener, sensor):
    # Its data is dropped on arrival, but the topic is watched: the sensor may
    # be assigned to a plant at any moment.
    assert sensor.plant is None
    assert listener.topics() == {"bonjour-plant/balcon/humidity"}


def test_a_deleted_sensor_is_not_listened_to(listener, sensor):
    sensor.is_deleted = True
    sensor.save()
    assert listener.topics() == set()


def test_a_sensor_without_a_topic_is_skipped(listener, sensor):
    sensor.mqtt_topic = ""
    sensor.save()
    assert listener.topics() == set()


def test_the_topics_follow_the_database(listener, sensor, growing_plant):
    Sensor.objects.create(name="Nouvelle sonde", model="Test", mqtt_topic="bonjour-plant/serre/temperature",
                          plant=growing_plant)
    assert listener.topics() == {"bonjour-plant/balcon/humidity", "bonjour-plant/serre/temperature"}
    sensor.mqtt_topic = "bonjour-plant/balcon/deplace"
    sensor.save()
    assert listener.topics() == {"bonjour-plant/balcon/deplace", "bonjour-plant/serre/temperature"}


# --- What we do with what arrives ---

def test_a_measure_of_an_assigned_sensor_is_recorded(listener, sensor, growing_plant):
    sensor.plant = growing_plant
    sensor.save()
    recorded = listener.handle_message("bonjour-plant/balcon/humidity", '{"humidity": 71.5}')
    assert len(recorded) == 1
    data = SensorData.objects.get()
    assert data.sensor == sensor
    assert data.plant == growing_plant
    assert data.payload == '{"humidity": 71.5}'
    assert data.time is not None


def test_a_measure_of_a_sensor_assigned_to_nothing_is_dropped(listener, sensor):
    assert sensor.plant is None
    assert listener.handle_message("bonjour-plant/balcon/humidity", '{"humidity": 40}') == []
    assert not SensorData.objects.exists()


def test_a_measure_on_a_topic_nobody_claims_is_dropped(listener, sensor, growing_plant):
    sensor.plant = growing_plant
    sensor.save()
    assert listener.handle_message("bonjour-plant/inconnu/truc", '{"bruit": 1}') == []
    assert not SensorData.objects.exists()


def test_a_measure_of_a_deleted_sensor_is_dropped(listener, sensor, growing_plant):
    sensor.plant = growing_plant
    sensor.is_deleted = True
    sensor.save()
    assert listener.handle_message("bonjour-plant/balcon/humidity", '{"humidity": 71.5}') == []
    assert not SensorData.objects.exists()


def test_a_wildcard_topic_catches_its_branch(listener, sensor, growing_plant):
    sensor.mqtt_topic = "bonjour-plant/+/humidity"
    sensor.plant = growing_plant
    sensor.save()
    assert len(listener.handle_message("bonjour-plant/serre/humidity", "42")) == 1
    assert listener.handle_message("bonjour-plant/serre/temperature", "19") == []


def test_two_sensors_on_the_same_topic_both_record(listener, sensor, growing_plant, harvested_plant):
    sensor.plant = growing_plant
    sensor.save()
    Sensor.objects.create(name="Sonde jumelle", model="Test", mqtt_topic=sensor.mqtt_topic, plant=harvested_plant)
    assert len(listener.handle_message(sensor.mqtt_topic, "42")) == 2
    assert SensorData.objects.count() == 2


def test_an_overlong_payload_is_cut_to_what_we_keep(listener, sensor, growing_plant):
    sensor.plant = growing_plant
    sensor.save()
    listener.handle_message(sensor.mqtt_topic, "x" * (MAX_PAYLOAD_LENGTH + 500))
    assert len(SensorData.objects.get().payload) == MAX_PAYLOAD_LENGTH


# --- Keeping the subscriptions in step ---

class FakeClient:
    """Records what the listener asks the broker, without a broker."""

    def __init__(self):
        self.subscribed, self.unsubscribed = [], []

    def subscribe(self, topic):
        self.subscribed.append(topic)

    def unsubscribe(self, topic):
        self.unsubscribed.append(topic)


def test_a_new_sensor_is_subscribed_to_on_the_next_sync(listener, sensor, growing_plant):
    client = FakeClient()
    listener.sync_subscriptions(client)
    assert client.subscribed == ["bonjour-plant/balcon/humidity"]

    Sensor.objects.create(name="Nouvelle sonde", model="Test", mqtt_topic="bonjour-plant/serre/temperature",
                          plant=growing_plant)
    listener.sync_subscriptions(client)
    # Only the newcomer is subscribed to: the first topic is left alone.
    assert client.subscribed == ["bonjour-plant/balcon/humidity", "bonjour-plant/serre/temperature"]
    assert client.unsubscribed == []


def test_a_deleted_sensor_is_unsubscribed_from_on_the_next_sync(listener, sensor):
    client = FakeClient()
    listener.sync_subscriptions(client)
    sensor.is_deleted = True
    sensor.save()
    listener.sync_subscriptions(client)
    assert client.unsubscribed == ["bonjour-plant/balcon/humidity"]
    assert listener.subscribed == set()


def test_a_retopiced_sensor_moves_its_subscription(listener, sensor):
    client = FakeClient()
    listener.sync_subscriptions(client)
    sensor.mqtt_topic = "bonjour-plant/balcon/deplace"
    sensor.save()
    listener.sync_subscriptions(client)
    assert client.subscribed == ["bonjour-plant/balcon/humidity", "bonjour-plant/balcon/deplace"]
    assert client.unsubscribed == ["bonjour-plant/balcon/humidity"]


def test_nothing_moves_when_the_database_has_not_changed(listener, sensor):
    client = FakeClient()
    listener.sync_subscriptions(client)
    listener.sync_subscriptions(client)
    assert client.subscribed == ["bonjour-plant/balcon/humidity"]
    assert client.unsubscribed == []


def test_a_reconnection_takes_every_subscription_again(listener, sensor):
    client = FakeClient()
    listener.sync_subscriptions(client)
    # A fresh connection carries no subscription.
    listener.subscribed = set()
    listener.sync_subscriptions(client)
    assert client.subscribed == ["bonjour-plant/balcon/humidity"] * 2
