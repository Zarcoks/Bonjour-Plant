"""The worker writing the measures of the sensors on the plants."""
import datetime

import pytest
from django.utils import timezone

from plant_management.models import Sensor, SensorData
from sync_worker import read_measures, sync_plants
from sync_worker.tasks import sync_sensors_to_plants


@pytest.fixture
def watched(sensor, growing_plant):
    """
    A sensor watching a plant, naming its measures the usual way.

    The planting date is dropped so that the progression cannot move: these
    tests are about the measures, and about them only.
    """
    growing_plant.planted_date = None
    growing_plant.save()
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
    assert read_measures(sensor, '{"humidity": 71, "luminosity": "high", "temperature": 21.5}') == {
        'current_humidity': 71,
        'current_luminosity': 3,
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


def test_the_five_light_levels_are_read(sensor):
    ranks = []
    for name in ["low-", "low", "nor", "high", "high+"]:
        ranks.append(read_measures(sensor, '{"luminosity": "%s"}' % name)['current_luminosity'])
    assert ranks == [0, 1, 2, 3, 4]


def test_a_level_is_read_whatever_its_case_and_padding(sensor):
    assert read_measures(sensor, '{"luminosity": " HIGH+ "}') == {'current_luminosity': 4}


def test_a_level_nobody_documented_is_left_out(sensor):
    assert read_measures(sensor, '{"luminosity": "brillant"}') == {}
    assert read_measures(sensor, '{"luminosity": 78}') == {}


def test_a_real_payload_of_the_sensor_is_read(sensor):
    # What the soil sensor actually publishes, keys and all.
    sensor.humidity_payload_label = "soil_moisture"
    sensor.luminosity_payload_label = "illuminance_level"
    assert read_measures(sensor, '{"battery":100,"illuminance_level":"low","linkquality":228,'
                                 '"soil_moisture":69,"temperature":27.7,"temperature_unit":"celsius"}') == {
        'current_humidity': 69,
        'current_luminosity': 1,
        'current_temperature': 27.7,
    }


# --- Writing on the plants ---

def test_the_last_measures_land_on_the_plant(watched, growing_plant):
    measure(watched, '{"humidity": 65, "luminosity": "high+", "temperature": 22.5}')
    assert sync_plants() == {'plants': 1, 'measures': 3, 'unreadable': 0, 'grown': 0}
    growing_plant.refresh_from_db()
    assert growing_plant.current_humidity == 65
    assert growing_plant.current_luminosity == 4
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
    assert sync_plants() == {'plants': 0, 'measures': 0, 'unreadable': 0, 'grown': 0}


def test_a_plant_whose_measures_have_not_moved_is_not_written_again(watched, growing_plant):
    measure(watched, '{"humidity": 65}')
    assert sync_plants()['plants'] == 1
    assert sync_plants() == {'plants': 0, 'measures': 0, 'unreadable': 0, 'grown': 0}


def test_a_deleted_plant_is_not_synchronised(watched, growing_plant):
    measure(watched, '{"humidity": 65}')
    growing_plant.is_deleted = True
    growing_plant.save()
    assert sync_plants()['plants'] == 0


def test_an_unreadable_payload_is_counted_and_skipped(watched, growing_plant):
    measure(watched, "pas du json")
    assert sync_plants() == {'plants': 0, 'measures': 0, 'unreadable': 1, 'grown': 0}
    growing_plant.refresh_from_db()
    assert growing_plant.current_humidity == 72


# --- The scheduled task ---

def test_the_task_synchronises(watched, growing_plant, db):
    measure(watched, '{"humidity": 65}')
    assert sync_sensors_to_plants() == {'plants': 1, 'measures': 1, 'unreadable': 0, 'grown': 0}
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


# --- How far along the plant is ---

def planted_days_ago(plant, days, harvest_days=60):
    """Plants it that long ago, on a species ready in that many days."""
    plant.plant_type.harvest_days = harvest_days
    plant.plant_type.save()
    plant.planted_date = timezone.now() - datetime.timedelta(days=days)
    plant.growing_state = 0
    plant.save()
    return plant


def test_the_progression_follows_the_calendar(db, growing_plant):
    planted_days_ago(growing_plant, 30, harvest_days=60)
    assert sync_plants() == {'plants': 1, 'measures': 0, 'unreadable': 0, 'grown': 1}
    growing_plant.refresh_from_db()
    assert growing_plant.growing_state == 50


def test_the_hour_counts_in_the_progression(db, growing_plant):
    growing_plant.plant_type.harvest_days = 2
    growing_plant.plant_type.save()
    growing_plant.planted_date = timezone.now() - datetime.timedelta(hours=12)
    growing_plant.growing_state = 0
    growing_plant.save()
    sync_plants()
    growing_plant.refresh_from_db()
    # Half a day of two: a quarter of the way, not nothing.
    assert growing_plant.growing_state == 25


def test_a_plant_left_past_its_harvest_stays_at_a_hundred(db, growing_plant):
    planted_days_ago(growing_plant, 200, harvest_days=60)
    sync_plants()
    growing_plant.refresh_from_db()
    assert growing_plant.growing_state == 100


def test_a_progression_that_has_not_moved_is_not_written_again(db, growing_plant):
    planted_days_ago(growing_plant, 30, harvest_days=60)
    assert sync_plants()['grown'] == 1
    assert sync_plants()['grown'] == 0


def test_a_harvested_plant_keeps_the_progression_it_had(db, harvested_plant):
    harvested_plant.plant_type.harvest_days = 60
    harvested_plant.plant_type.save()
    harvested_plant.planted_date = timezone.now() - datetime.timedelta(days=200)
    harvested_plant.growing_state = 80
    harvested_plant.save()
    assert sync_plants()['grown'] == 0
    harvested_plant.refresh_from_db()
    assert harvested_plant.growing_state == 80


def test_a_plant_without_a_planting_date_has_no_progression(db, growing_plant):
    growing_plant.planted_date = None
    growing_plant.growing_state = 42
    growing_plant.save()
    assert sync_plants()['grown'] == 0
    growing_plant.refresh_from_db()
    assert growing_plant.growing_state == 42


def test_a_species_without_a_harvest_delay_has_no_progression(db, growing_plant):
    planted_days_ago(growing_plant, 30, harvest_days=0)
    assert sync_plants()['grown'] == 0


def test_a_plant_planted_in_the_future_is_at_nothing(db, growing_plant):
    planted_days_ago(growing_plant, -10, harvest_days=60)
    growing_plant.growing_state = 50
    growing_plant.save()
    sync_plants()
    growing_plant.refresh_from_db()
    assert growing_plant.growing_state == 0


def test_measures_and_progression_are_written_together(watched, growing_plant):
    planted_days_ago(growing_plant, 30, harvest_days=60)
    measure(watched, '{"humidity": 65}')
    assert sync_plants() == {'plants': 1, 'measures': 1, 'unreadable': 0, 'grown': 1}
    growing_plant.refresh_from_db()
    assert (growing_plant.current_humidity, growing_plant.growing_state) == (65, 50)
