"""Spotting a watering in what the sensors report."""
import datetime

import pytest

from mqtt_worker import SensorListener, broker_from_url, watering
from plant_management.models import AppLog, SensorData


@pytest.fixture
def watched(sensor, growing_plant):
    sensor.plant = growing_plant
    sensor.save()
    return sensor


def measure(sensor, humidity, minutes_ago=0):
    """Records a humidity as if it had arrived that long ago."""
    data = SensorData.objects.create(sensor=sensor, plant=sensor.plant,
                                    payload='{"humidity": %s}' % humidity)
    if minutes_ago:
        SensorData.objects.filter(pk=data.pk).update(time=data.time - datetime.timedelta(minutes=minutes_ago))
        data.refresh_from_db()
    return data


# --- What counts as a watering ---

def test_a_jump_of_humidity_is_a_watering(watched, growing_plant):
    measure(watched, 40, minutes_ago=5)
    assert watering.spot(watched, measure(watched, 60)) is True
    growing_plant.refresh_from_db()
    assert growing_plant.last_watering.date() == datetime.datetime.now().date()


def test_the_rise_has_to_be_worth_more_than_the_threshold(watched, growing_plant):
    before = growing_plant.last_watering
    measure(watched, 40, minutes_ago=5)
    # Exactly the threshold is not more than the threshold.
    assert watering.spot(watched, measure(watched, 40 + watering.HUMIDITY_RISE)) is False
    growing_plant.refresh_from_db()
    assert growing_plant.last_watering == before


def test_humidity_going_down_is_not_a_watering(watched, growing_plant):
    # The soil drying out, which is the opposite.
    measure(watched, 70, minutes_ago=5)
    assert watering.spot(watched, measure(watched, 40)) is False


def test_a_jump_between_two_close_measures_is_not_a_watering(watched, growing_plant):
    # Two minutes apart: nothing to compare with, yet.
    measure(watched, 40, minutes_ago=2)
    assert watering.spot(watched, measure(watched, 70)) is False


def test_the_measure_compared_with_is_the_last_one_old_enough(watched, growing_plant):
    measure(watched, 20, minutes_ago=30)   # long ago, and much drier
    measure(watched, 65, minutes_ago=4)    # the one to compare with
    assert watering.spot(watched, measure(watched, 70)) is False


def test_a_first_measure_is_not_a_watering(watched, growing_plant):
    assert watering.spot(watched, measure(watched, 70)) is False


def test_a_payload_without_humidity_says_nothing(watched, growing_plant):
    measure(watched, 40, minutes_ago=5)
    data = SensorData.objects.create(sensor=watched, plant=growing_plant, payload='{"temperature": 21}')
    assert watering.spot(watched, data) is False


def test_an_unreadable_measure_before_says_nothing(watched, growing_plant):
    SensorData.objects.filter(
        pk=SensorData.objects.create(sensor=watched, plant=growing_plant, payload="pas du json").pk
    ).update(time=datetime.datetime.now() - datetime.timedelta(minutes=5))
    assert watering.spot(watched, measure(watched, 70)) is False


def test_the_keys_of_the_sensor_are_the_ones_read(watched, growing_plant):
    watched.humidity_payload_label = "soil_moisture"
    watched.save()
    old = SensorData.objects.create(sensor=watched, plant=growing_plant, payload='{"soil_moisture": 40}')
    SensorData.objects.filter(pk=old.pk).update(time=old.time - datetime.timedelta(minutes=5))
    fresh = SensorData.objects.create(sensor=watched, plant=growing_plant, payload='{"soil_moisture": 70}')
    assert watering.spot(watched, fresh) is True


def test_a_sensor_assigned_to_nothing_waters_nothing(sensor, growing_plant):
    assert sensor.plant is None
    data = SensorData.objects.create(sensor=sensor, plant=growing_plant, payload='{"humidity": 70}')
    assert watering.spot(sensor, data) is False


def test_the_history_of_another_plant_is_not_compared_with(watched, growing_plant, harvested_plant):
    # The sensor watched another plant before: its humidity there says nothing here.
    SensorData.objects.filter(
        pk=SensorData.objects.create(sensor=watched, plant=harvested_plant, payload='{"humidity": 40}').pk
    ).update(time=datetime.datetime.now() - datetime.timedelta(minutes=5))
    assert watering.spot(watched, measure(watched, 70)) is False


def test_a_watering_is_written_in_the_journal(watched, growing_plant):
    measure(watched, 40, minutes_ago=5)
    watering.spot(watched, measure(watched, 60))
    assert AppLog.objects.filter(type="INFO", message__contains="Arrosage détecté").count() == 1


# --- Through the listener, as a measure arrives ---

def test_a_measure_arriving_spots_the_watering(watched, growing_plant):
    listener = SensorListener(broker=broker_from_url("mqtt://broker:1883"), sync_seconds=1)
    measure(watched, 40, minutes_ago=5)
    listener.handle_message(watched.mqtt_topic, '{"humidity": 62}')
    growing_plant.refresh_from_db()
    assert growing_plant.last_watering is not None
    assert growing_plant.last_watering.date() == datetime.datetime.now().date()


def test_a_measure_arriving_without_a_jump_leaves_the_watering_alone(watched, growing_plant):
    was = growing_plant.last_watering
    listener = SensorListener(broker=broker_from_url("mqtt://broker:1883"), sync_seconds=1)
    measure(watched, 40, minutes_ago=5)
    listener.handle_message(watched.mqtt_topic, '{"humidity": 44}')
    growing_plant.refresh_from_db()
    assert growing_plant.last_watering == was
