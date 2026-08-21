"""The decisions the application takes on its own."""
import datetime

import pytest

from decision_worker import light_the_plants, water_the_plants
from decision_worker import tasks
from plant_management.models import Actionner, AppLog, PlantType

MIDDAY = datetime.time(12, 0)
NIGHT = datetime.time(23, 0)


@pytest.fixture
def lit_plant(growing_plant):
    """A plant whose light is left to the application, wanting it from 8 to 20."""
    growing_plant.auto_luminosity = True
    growing_plant.save()
    growing_plant.plant_type.light_starts_at = datetime.time(8, 0)
    growing_plant.plant_type.light_ends_at = datetime.time(20, 0)
    growing_plant.plant_type.save()
    return growing_plant


@pytest.fixture
def lamp(lit_plant):
    return Actionner.objects.create(name="Lampe UV", act_on="luminosity", plant=lit_plant,
                                    mqtt_topic="bonjour-plant/balcon/lampe/set", is_on=False)


# --- Inside and outside the window ---

def test_the_lamp_is_switched_on_inside_the_window(lamp):
    assert light_the_plants(at=MIDDAY) == {'switched_on': 1, 'switched_off': 0}
    lamp.refresh_from_db()
    assert lamp.is_on
    assert lamp.last_switch is not None


def test_the_lamp_is_switched_off_outside_the_window(lamp):
    lamp.is_on = True
    lamp.save()
    assert light_the_plants(at=NIGHT) == {'switched_on': 0, 'switched_off': 1}
    lamp.refresh_from_db()
    assert not lamp.is_on


def test_the_window_opens_on_its_first_minute(lamp):
    light_the_plants(at=datetime.time(8, 0))
    lamp.refresh_from_db()
    assert lamp.is_on


def test_the_window_is_over_on_its_last_minute(lamp):
    lamp.is_on = True
    lamp.save()
    light_the_plants(at=datetime.time(20, 0))
    lamp.refresh_from_db()
    assert not lamp.is_on


def test_a_lamp_already_in_the_right_state_is_left_alone(lamp):
    lamp.is_on = True
    lamp.last_switch = None
    lamp.save()
    assert light_the_plants(at=MIDDAY) == {'switched_on': 0, 'switched_off': 0}
    lamp.refresh_from_db()
    # Not written again, so the date of the last switch stays as it was.
    assert lamp.last_switch is None


# --- What is left alone ---

def test_a_plant_whose_light_is_not_automatic_is_left_alone(lamp, lit_plant):
    lit_plant.auto_luminosity = False
    lit_plant.save()
    assert light_the_plants(at=MIDDAY) == {'switched_on': 0, 'switched_off': 0}
    lamp.refresh_from_db()
    assert not lamp.is_on


def test_an_actionner_acting_on_something_else_is_left_alone(lit_plant):
    humidifier = Actionner.objects.create(name="Brumisateur", act_on="humidity", plant=lit_plant,
                                          mqtt_topic="bonjour-plant/serre/brumisateur/set")
    light_the_plants(at=MIDDAY)
    humidifier.refresh_from_db()
    assert not humidifier.is_on


def test_a_deleted_actionner_is_left_alone(lamp):
    lamp.is_deleted = True
    lamp.save()
    assert light_the_plants(at=MIDDAY) == {'switched_on': 0, 'switched_off': 0}
    lamp.refresh_from_db()
    assert not lamp.is_on


def test_an_actionner_of_no_plant_is_left_alone(db, lit_plant):
    free = Actionner.objects.create(name="Prise libre", act_on="luminosity",
                                    mqtt_topic="bonjour-plant/atelier/prise/set")
    light_the_plants(at=MIDDAY)
    free.refresh_from_db()
    assert not free.is_on


def test_a_deleted_plant_is_left_alone(lamp, lit_plant):
    lit_plant.is_deleted = True
    lit_plant.save()
    assert light_the_plants(at=MIDDAY) == {'switched_on': 0, 'switched_off': 0}


def test_a_plant_without_a_lamp_decides_nothing(lit_plant):
    assert light_the_plants(at=MIDDAY) == {'switched_on': 0, 'switched_off': 0}


# --- Several plugs, several plants ---

def test_every_lamp_of_a_plant_follows(lamp, lit_plant):
    second = Actionner.objects.create(name="Seconde lampe", act_on="luminosity", plant=lit_plant,
                                      mqtt_topic="bonjour-plant/balcon/lampe2/set")
    assert light_the_plants(at=MIDDAY)['switched_on'] == 2
    second.refresh_from_db()
    assert second.is_on


def test_each_plant_follows_its_own_window(lamp, lit_plant, harvested_plant):
    # Its own species, otherwise both plants would share the same window.
    harvested_plant.plant_type = PlantType.objects.create(
        plant_name="Champignon", humidity_min=70, humidity_max=90, temperature_min=12.0,
        temperature_max=20.0, harvest_days=30,
        light_starts_at=datetime.time(21, 0), light_ends_at=datetime.time(23, 30))
    harvested_plant.auto_luminosity = True
    harvested_plant.save()
    night_lamp = Actionner.objects.create(name="Lampe de nuit", act_on="luminosity",
                                          plant=harvested_plant, mqtt_topic="nuit/set")

    light_the_plants(at=MIDDAY)
    lamp.refresh_from_db()
    night_lamp.refresh_from_db()
    assert lamp.is_on and not night_lamp.is_on


# --- What the journal keeps ---

def test_each_switch_is_written_in_the_journal(lamp):
    light_the_plants(at=MIDDAY)
    written = AppLog.objects.get(type="INFO")
    assert "Lumière automatique" in written.message
    assert "Lampe UV" in written.message
    assert "allumé" in written.message


def test_a_decision_that_changes_nothing_says_nothing(lamp, db):
    lamp.is_on = True
    lamp.save()
    light_the_plants(at=MIDDAY)
    assert not AppLog.objects.exists()


# --- Watering the plants ---

@pytest.fixture
def dry_plant(growing_plant):
    """
    A plant whose watering is left to the application, drying up.

    Its species is kept at (60 + 80) / 2 = 70 % of humidity, and it reports 55.
    """
    growing_plant.auto_watering = True
    growing_plant.current_humidity = 55
    growing_plant.save()
    return growing_plant


@pytest.fixture
def humidifier(dry_plant):
    return Actionner.objects.create(name="Brumisateur", act_on="humidity", plant=dry_plant,
                                    mqtt_topic="bonjour-plant/serre/brumisateur/set", is_on=False)


def test_a_plant_below_the_middle_of_its_range_is_watered(humidifier):
    assert water_the_plants() == {'switched_on': 1, 'switched_off': 0}
    humidifier.refresh_from_db()
    assert humidifier.is_on
    assert humidifier.last_switch is not None


def test_a_plant_above_the_middle_of_its_range_stops_being_watered(humidifier, dry_plant):
    dry_plant.current_humidity = 78
    dry_plant.save()
    humidifier.is_on = True
    humidifier.save()
    assert water_the_plants() == {'switched_on': 0, 'switched_off': 1}
    humidifier.refresh_from_db()
    assert not humidifier.is_on


def test_a_plant_right_on_the_middle_is_not_watered(humidifier, dry_plant):
    # 70 % is what the species is kept at: watering starts below it, not at it.
    dry_plant.current_humidity = 70
    dry_plant.save()
    assert water_the_plants() == {'switched_on': 0, 'switched_off': 0}
    humidifier.refresh_from_db()
    assert not humidifier.is_on


def test_a_plant_that_never_reported_its_humidity_is_not_watered(humidifier, dry_plant):
    dry_plant.current_humidity = None
    dry_plant.save()
    humidifier.is_on = True
    humidifier.save()
    # Nothing is left running on a measure we do not have.
    assert water_the_plants() == {'switched_on': 0, 'switched_off': 1}
    humidifier.refresh_from_db()
    assert not humidifier.is_on


def test_a_humidifier_already_in_the_right_state_is_left_alone(humidifier):
    humidifier.is_on = True
    humidifier.last_switch = None
    humidifier.save()
    assert water_the_plants() == {'switched_on': 0, 'switched_off': 0}
    humidifier.refresh_from_db()
    assert humidifier.last_switch is None


def test_a_plant_whose_watering_is_not_automatic_is_left_alone(humidifier, dry_plant):
    dry_plant.auto_watering = False
    dry_plant.save()
    assert water_the_plants() == {'switched_on': 0, 'switched_off': 0}
    humidifier.refresh_from_db()
    assert not humidifier.is_on


def test_an_actionner_acting_on_something_else_is_left_dry(dry_plant):
    lamp = Actionner.objects.create(name="Lampe UV", act_on="luminosity", plant=dry_plant,
                                    mqtt_topic="bonjour-plant/balcon/lampe/set")
    water_the_plants()
    lamp.refresh_from_db()
    assert not lamp.is_on


def test_a_deleted_humidifier_is_left_alone(humidifier):
    humidifier.is_deleted = True
    humidifier.save()
    assert water_the_plants() == {'switched_on': 0, 'switched_off': 0}
    humidifier.refresh_from_db()
    assert not humidifier.is_on


def test_a_humidifier_of_no_plant_is_left_alone(db, dry_plant):
    free = Actionner.objects.create(name="Prise libre", act_on="humidity",
                                    mqtt_topic="bonjour-plant/atelier/prise/set")
    water_the_plants()
    free.refresh_from_db()
    assert not free.is_on


def test_a_deleted_plant_is_never_watered(humidifier, dry_plant):
    dry_plant.is_deleted = True
    dry_plant.save()
    assert water_the_plants() == {'switched_on': 0, 'switched_off': 0}


def test_every_humidifier_of_a_plant_follows(humidifier, dry_plant):
    second = Actionner.objects.create(name="Second brumisateur", act_on="humidity", plant=dry_plant,
                                      mqtt_topic="bonjour-plant/serre/brumisateur2/set")
    assert water_the_plants()['switched_on'] == 2
    second.refresh_from_db()
    assert second.is_on


def test_each_plant_follows_the_range_of_its_own_species(humidifier, dry_plant, harvested_plant):
    # Kept at (20 + 40) / 2 = 30 %, which the same 55 % of humidity is well above.
    harvested_plant.plant_type = PlantType.objects.create(
        plant_name="Cactus", humidity_min=20, humidity_max=40, temperature_min=15.0,
        temperature_max=35.0, harvest_days=200)
    harvested_plant.auto_watering = True
    harvested_plant.current_humidity = 55
    harvested_plant.save()
    cactus_mister = Actionner.objects.create(name="Brumisateur du cactus", act_on="humidity",
                                             plant=harvested_plant, mqtt_topic="cactus/set")

    water_the_plants()
    humidifier.refresh_from_db()
    cactus_mister.refresh_from_db()
    assert humidifier.is_on and not cactus_mister.is_on


def test_each_watering_switch_is_written_in_the_journal(humidifier):
    water_the_plants()
    written = AppLog.objects.get(type="INFO")
    assert "Arrosage automatique" in written.message
    assert "Brumisateur" in written.message
    assert "allumé" in written.message


def test_a_watering_decision_that_changes_nothing_says_nothing(humidifier, db):
    humidifier.is_on = True
    humidifier.save()
    water_the_plants()
    assert not AppLog.objects.exists()


# --- The scheduled task ---

def test_the_task_takes_every_decision(lamp, humidifier):
    # No hour given: the task decides on the hour it runs at.
    summary = tasks.take_the_decisions()
    assert set(summary) == {'light', 'watering'}
    assert set(summary['light']) == {'switched_on', 'switched_off'}
    # Both decisions ran: the dry plant was watered whatever the hour is.
    assert summary['watering'] == {'switched_on': 1, 'switched_off': 0}
