"""The worker writing the measures of the sensors on the plants."""
import datetime

import pytest

from plant_management.models import GrowingPlant, Sensor, SensorData
from sync_worker import read_measures, sync_plants
from sync_worker.tasks import sync_sensors_to_plants


@pytest.fixture
def watched(sensor, growing_plant):
    """A sensor watching a plant, naming its measures the usual way."""
    sensor.plant = growing_plant
    sensor.save()
    return sensor


def measure(sensor, payload, minutes_ago=0):
    """Records a payload as if it had arrived that long ago."""
    data = SensorData.objects.create(sensor=sensor, plant=sensor.plant, payload=payload)
    if minutes_ago:
        moment = data.time - datetime.timedelta(minutes=minutes_ago)
        SensorData.objects.filter(pk=data.pk).update(time=moment)
        data.refresh_from_db()
    return data


# --- Reading a payload ---

def test_the_usual_names_are_read(sensor):
    assert read_measures(sensor, '{"humidity": 71, "luminosity": 8, "temperature": 21.5}') == {
        'current_humidity': 71,
        'current_luminosity': 8,
        'current_temperature': 21.5,
    }


def test_the_names_of_the_sensor_are_the_ones_read(sensor):
    sensor.humidity_payload_label = "hum"
    sensor.temperature_payload_label = "temp"
    assert read_measures(sensor, '{"hum": 60, "temp": 19}') == {
        'current_humidity': 60,
        'current_temperature': 19.0,
    }
    # The usual names mean nothing to this sensor any more.
    assert read_measures(sensor, '{"humidity": 60}') == {}


def test_a_key_the_payload_does_not_carry_is_left_out(sensor):
    assert read_measures(sensor, '{"humidity": 71}') == {'current_humidity': 71}


def test_numbers_written_as_text_are_read(sensor):
    assert read_measures(sensor, '{"humidity": "71.4", "temperature": "19,5"}') == {'current_humidity': 71}


def test_a_humidity_is_rounded_and_a_temperature_is_not(sensor):
    read = read_measures(sensor, '{"humidity": 71.6, "temperature": 19.45}')
    assert read == {'current_humidity': 72, 'current_temperature': 19.45}


def test_a_payload_that_is_not_json_is_refused(sensor):
    assert read_measures(sensor, "pas du json") is None
    assert read_measures(sensor, "") is None


def test_a_json_payload_that_is_not_an_object_is_refused(sensor):
    # Valid JSON, but nothing to read a measure from.
    assert read_measures(sensor, '[1, 2, 3]') is None
    assert read_measures(sensor, "71.5") is None


# --- Writing on the plants ---

def test_the_last_measures_land_on_the_plant(watched, growing_plant):
    measure(watched, '{"humidity": 65, "luminosity": 9, "temperature": 22.5}')
    assert sync_plants() == {'plants': 1, 'measures': 3, 'unreadable': 0}
    growing_plant.refresh_from_db()
    assert growing_plant.current_humidity == 65
    assert growing_plant.current_luminosity == 9
    assert growing_plant.current_temperature == 22.5


def test_only_the_latest_payload_of_a_sensor_counts(watched, growing_plant):
    # Written in the opposite order of their moment: the freshest measure wins,
    # whatever the order the rows were inserted in.
    measure(watched, '{"humidity": 65}')
    measure(watched, '{"humidity": 30}', minutes_ago=10)
    sync_plants()
    growing_plant.refresh_from_db()
    assert growing_plant.current_humidity == 65


def test_several_sensors_each_bring_their_own_measure(watched, growing_plant):
    thermometer = Sensor.objects.create(name="Thermomètre", model="Test", mqtt_topic="serre",
                                        plant=growing_plant, temperature_payload_label="temp")
    measure(watched, '{"humidity": 65}')
    measure(thermometer, '{"temp": 26.5}')
    sync_plants()
    growing_plant.refresh_from_db()
    assert growing_plant.current_humidity == 65
    assert growing_plant.current_temperature == 26.5


def test_the_freshest_of_two_sensors_wins(watched, growing_plant):
    other = Sensor.objects.create(name="Seconde sonde", model="Test", mqtt_topic="autre", plant=growing_plant)
    measure(watched, '{"humidity": 30}', minutes_ago=5)
    measure(other, '{"humidity": 70}')
    sync_plants()
    growing_plant.refresh_from_db()
    assert growing_plant.current_humidity == 70


def test_a_deleted_sensor_is_not_listened_to(watched, growing_plant):
    measure(watched, '{"humidity": 65}')
    watched.is_deleted = True
    watched.save()
    assert sync_plants()['plants'] == 0
    growing_plant.refresh_from_db()
    assert growing_plant.current_humidity == 72  # the value of the fixture, untouched


def test_a_plant_without_any_data_is_left_alone(watched, growing_plant):
    assert sync_plants() == {'plants': 0, 'measures': 0, 'unreadable': 0}


def test_a_plant_whose_measures_have_not_moved_is_not_written_again(watched, growing_plant):
    measure(watched, '{"humidity": 65}')
    assert sync_plants()['plants'] == 1
    assert sync_plants() == {'plants': 0, 'measures': 0, 'unreadable': 0}


def test_a_deleted_plant_is_not_synchronised(watched, growing_plant):
    measure(watched, '{"humidity": 65}')
    growing_plant.is_deleted = True
    growing_plant.save()
    assert sync_plants()['plants'] == 0


def test_an_unreadable_payload_is_counted_and_skipped(watched, growing_plant):
    measure(watched, "pas du json")
    assert sync_plants() == {'plants': 0, 'measures': 0, 'unreadable': 1}
    growing_plant.refresh_from_db()
    assert growing_plant.current_humidity == 72


# --- The scheduled task ---

def test_the_task_synchronises(watched, growing_plant, db):
    measure(watched, '{"humidity": 65}')
    assert sync_sensors_to_plants() == {'plants': 1, 'measures': 1, 'unreadable': 0}
    growing_plant.refresh_from_db()
    assert growing_plant.current_humidity == 65


def test_a_synchronisation_that_went_well_says_nothing(watched, growing_plant, db):
    from plant_management.models import AppLog

    # Nothing to report on a normal run, whether measures moved or not.
    measure(watched, '{"humidity": 65}')
    sync_sensors_to_plants()
    sync_sensors_to_plants()
    assert not AppLog.objects.exists()


def test_the_task_warns_about_unreadable_payloads(watched, growing_plant, db):
    from plant_management.models import AppLog

    measure(watched, "pas du json")
    sync_sensors_to_plants()
    assert AppLog.objects.filter(type="WARNING", message__contains="illisible").count() == 1
