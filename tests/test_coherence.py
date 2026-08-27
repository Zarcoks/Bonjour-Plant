"""Checking that what a plug is asked to do shows up in the measures."""
import datetime

import pytest
from django.urls import reverse

from coherence_worker import check_the_actionners, drift_of
from coherence_worker import checks, tasks
from mqtt_worker import feedback
from plant_management.models import Actionner, AppLog, SensorData


@pytest.fixture
def watched(sensor, growing_plant):
    """A sensor watching the plant."""
    sensor.plant = growing_plant
    sensor.save()
    return sensor


@pytest.fixture
def lamp(growing_plant, db):
    """A lamp of that plant, off, which the application believes in."""
    return Actionner.objects.create(name="Lampe UV", act_on="luminosity", plant=growing_plant,
                                    mqtt_topic_out="bonjour-plant/balcon/lampe/set")


@pytest.fixture
def humidifier(growing_plant, db):
    """A humidifier of that plant, off, which the application believes in."""
    return Actionner.objects.create(name="Brumisateur", act_on="humidity", plant=growing_plant,
                                    mqtt_topic_out="bonjour-plant/serre/brumisateur/set")


def lit(sensor, level, minutes_ago=0, label='luminosity'):
    """Records a level of light as if it had arrived that long ago."""
    data = SensorData.objects.create(sensor=sensor, plant=sensor.plant,
                                     payload='{"%s": "%s"}' % (label, level))
    if minutes_ago:
        SensorData.objects.filter(pk=data.pk).update(
            time=data.time - datetime.timedelta(minutes=minutes_ago))
        data.refresh_from_db()
    return data


# --- A lamp that is on while the light stays low ---

def test_a_lamp_that_is_on_while_the_light_stays_low_is_warned_about(lamp, watched):
    lamp.is_on = True
    lamp.save()
    lit(watched, "low")
    assert drift_of(lamp) == "est allumé, mais la luminosité reste faible"


def test_a_lamp_that_is_on_while_the_light_is_only_normal_is_warned_about(lamp, watched):
    lamp.is_on = True
    lamp.save()
    lit(watched, "nor")
    assert drift_of(lamp) == "est allumé, mais la luminosité reste normale"


def test_a_lamp_that_is_on_in_the_dark_is_warned_about(lamp, watched):
    lamp.is_on = True
    lamp.save()
    lit(watched, "low-")
    assert drift_of(lamp) == "est allumé, mais la luminosité reste très faible"


def test_a_lamp_that_is_on_with_a_high_level_says_nothing(lamp, watched):
    lamp.is_on = True
    lamp.save()
    lit(watched, "high")
    assert drift_of(lamp) is None


def test_a_lamp_that_is_on_in_full_light_says_nothing(lamp, watched):
    # A plant already at "très forte" has nowhere higher to go.
    lamp.is_on = True
    lamp.save()
    lit(watched, "high+")
    assert drift_of(lamp) is None


# --- A lamp that is off while the light is high ---

def test_a_lamp_that_is_off_in_full_light_is_warned_about(lamp, watched):
    lit(watched, "high+")
    assert drift_of(lamp) == "est éteint, mais la luminosité est très forte"


def test_a_lamp_that_is_off_with_a_high_level_is_warned_about(lamp, watched):
    lit(watched, "high")
    assert drift_of(lamp) == "est éteint, mais la luminosité est forte"


def test_a_lamp_that_is_off_in_a_normal_light_says_nothing(lamp, watched):
    lit(watched, "nor")
    assert drift_of(lamp) is None


def test_a_lamp_that_is_off_in_the_shade_says_nothing(lamp, watched):
    lit(watched, "low-")
    assert drift_of(lamp) is None


# --- What cannot be judged ---

def test_a_plug_acting_on_something_else_than_light_is_not_judged(humidifier, watched):
    # Humidity and temperature are not judged: only a lamp is.
    humidifier.is_on = True
    humidifier.save()
    SensorData.objects.create(sensor=watched, plant=watched.plant, payload='{"humidity": 20}')
    assert drift_of(humidifier) is None


def test_a_plug_assigned_to_no_plant_is_not_judged(actionner, watched):
    assert actionner.plant is None
    assert drift_of(actionner) is None


def test_a_plant_without_a_reading_is_not_judged(lamp):
    assert drift_of(lamp) is None


def test_a_measure_the_sensors_do_not_report_is_not_judged(lamp, watched):
    SensorData.objects.create(sensor=watched, plant=watched.plant, payload='{"humidity": 70}')
    # Something was measured, but nothing says anything about the light.
    assert drift_of(lamp) is None


def test_readings_that_stopped_coming_are_not_judged(lamp, watched):
    lamp.is_on = True
    lamp.save()
    lit(watched, "low", minutes_ago=int(checks.STALE_AFTER.total_seconds() / 60) + 1)
    # A sensor that stopped talking is not a lamp that stopped working.
    assert drift_of(lamp) is None


def test_a_level_off_the_scale_is_no_judgement(lamp, watched):
    lamp.is_on = True
    lamp.save()
    # What an older reading in percent would leave behind.
    SensorData.objects.create(sensor=watched, plant=watched.plant, payload='{"luminosity": 78}')
    assert drift_of(lamp) is None


# --- Reading the payload ---

def test_a_lamp_is_judged_on_one_reading_alone(lamp, watched):
    lamp.is_on = True
    lamp.save()
    lit(watched, "low")
    assert SensorData.objects.count() == 1
    # The level speaks for itself: nothing to compare it with.
    assert drift_of(lamp) == "est allumé, mais la luminosité reste faible"


def test_the_measure_is_read_with_the_keys_of_its_sensor(lamp, watched):
    watched.luminosity_payload_label = "illuminance_level"
    watched.save()
    lamp.is_on = True
    lamp.save()
    lit(watched, "low", label="illuminance_level")
    # Read under the key this sensor uses, so the level is seen at all.
    assert drift_of(lamp) == "est allumé, mais la luminosité reste faible"


def test_a_sensor_naming_its_measure_otherwise_is_not_read_by_the_usual_key(lamp, watched):
    watched.luminosity_payload_label = "illuminance_level"
    watched.save()
    lamp.is_on = True
    lamp.save()
    lit(watched, "low")
    # Written under "luminosity", which this sensor does not use: nothing to judge on.
    assert drift_of(lamp) is None


def test_a_reading_that_carries_nothing_is_skipped(lamp, watched):
    lamp.is_on = True
    lamp.save()
    lit(watched, "low")
    # A payload with no light in it does not hide the one behind it.
    SensorData.objects.create(sensor=watched, plant=watched.plant, payload='{"temperature": 21}')
    assert drift_of(lamp) == "est allumé, mais la luminosité reste faible"


# --- The pass over every plug ---

def test_the_pass_warns_about_the_plugs_that_are_belied(lamp, watched):
    lamp.is_on = True
    lamp.save()
    lit(watched, "low")
    assert check_the_actionners() == {'checked': 1, 'warned': 1}
    warning = feedback.standing()[0]
    assert warning['name'] == "Lampe UV"
    assert warning['kind'] == feedback.KIND_EFFECT


def test_the_pass_leaves_the_plugs_that_add_up_alone(lamp, watched):
    lamp.is_on = True
    lamp.save()
    lit(watched, "high+")
    assert check_the_actionners() == {'checked': 1, 'warned': 0}
    assert feedback.standing() == []


def test_a_plug_of_no_plant_is_not_even_looked_at(actionner, lamp, watched):
    lit(watched, "high+")
    assert check_the_actionners()['checked'] == 1


def test_a_deleted_plug_is_not_looked_at(lamp, watched):
    lamp.is_deleted = True
    lamp.save()
    lit(watched, "high+")
    assert check_the_actionners() == {'checked': 0, 'warned': 0}


def test_nothing_is_switched_by_the_check(lamp, watched):
    lit(watched, "high+")
    check_the_actionners()
    lamp.refresh_from_db()
    # What the plugs do is the user's business: the worker only says so.
    assert not lamp.is_on


def test_the_warning_is_written_in_the_journal_once(lamp, watched):
    lit(watched, "high+")
    check_the_actionners()
    check_the_actionners()
    written = AppLog.objects.get(type="WARNING")
    assert "Lampe UV" in written.message
    assert "est éteint, mais la luminosité est très forte" in written.message


def test_the_warning_stands_beside_the_one_about_the_state(lamp, watched):
    lit(watched, "high+")
    check_the_actionners()
    feedback.warn(lamp, feedback.KIND_STATE, "se dit allumé")
    # Two ways of belying the application, two warnings to settle.
    assert {warning['kind'] for warning in feedback.standing()} == {feedback.KIND_STATE,
                                                                    feedback.KIND_EFFECT}


def test_settling_one_kind_leaves_the_other(client, lamp, watched):
    lit(watched, "high+")
    check_the_actionners()
    feedback.warn(lamp, feedback.KIND_STATE, "se dit allumé")
    client.post(reverse("dismiss_warning",
                        kwargs={"subject": "actionner", "device_id": lamp.pk,
                                "kind": feedback.KIND_STATE}))
    assert [warning['kind'] for warning in feedback.standing()] == [feedback.KIND_EFFECT]


def test_the_warning_shows_on_the_main_page(client, lamp, watched):
    lit(watched, "high+")
    check_the_actionners()
    content = client.get(reverse("growing_plants")).content.decode()
    assert "Lampe UV" in content
    assert "la luminosité est très forte" in content


# --- The scheduled task ---

def test_the_task_checks_the_plugs(lamp, watched):
    lit(watched, "low")
    lamp.is_on = True
    lamp.save()
    assert tasks.check_the_plugs() == {'checked': 1, 'warned': 1}
