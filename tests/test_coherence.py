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
    """A humidity sensor watching the plant."""
    sensor.plant = growing_plant
    sensor.save()
    return sensor


@pytest.fixture
def humidifier(growing_plant, db):
    """A humidifier of that plant, off, which the application believes in."""
    return Actionner.objects.create(name="Brumisateur", act_on="humidity", plant=growing_plant,
                                    mqtt_topic_out="bonjour-plant/serre/brumisateur/set")


def measure(sensor, humidity, minutes_ago=0, label='humidity'):
    """Records a humidity as if it had arrived that long ago."""
    data = SensorData.objects.create(sensor=sensor, plant=sensor.plant,
                                     payload='{"%s": %s}' % (label, humidity))
    if minutes_ago:
        SensorData.objects.filter(pk=data.pk).update(
            time=data.time - datetime.timedelta(minutes=minutes_ago))
        data.refresh_from_db()
    return data


def rising(sensor, by):
    """Two measures far enough apart, the second higher by that much."""
    measure(sensor, 50, minutes_ago=6)
    measure(sensor, 50 + by)


# --- A plug that is off while the measure climbs ---

def test_a_plug_that_is_off_while_the_measure_climbs_is_warned_about(humidifier, watched):
    rising(watched, checks.SIGNIFICANT_RISE['humidity'])
    drift = drift_of(humidifier)
    assert drift.startswith("est éteint, mais l'humidité monte quand même")
    assert "50 %" in drift and "55 %" in drift


def test_a_rise_under_the_threshold_says_nothing(humidifier, watched):
    rising(watched, checks.SIGNIFICANT_RISE['humidity'] - 1)
    assert drift_of(humidifier) is None


def test_a_plug_that_is_off_while_the_measure_falls_says_nothing(humidifier, watched):
    rising(watched, -20)
    assert drift_of(humidifier) is None


# --- A plug that is on while the measure does not follow ---

def test_a_plug_that_is_on_while_the_measure_falls_is_warned_about(humidifier, watched):
    humidifier.is_on = True
    humidifier.save()
    rising(watched, -8)
    drift = drift_of(humidifier)
    assert drift.startswith("est allumé, mais l'humidité ne monte pas")


def test_a_plug_that_is_on_while_the_measure_holds_is_warned_about(humidifier, watched):
    humidifier.is_on = True
    humidifier.save()
    rising(watched, 0)
    # Holding still is not acting: a humidifier that runs makes the humidity move.
    assert drift_of(humidifier) is not None


def test_a_plug_that_is_on_while_the_measure_climbs_says_nothing(humidifier, watched):
    humidifier.is_on = True
    humidifier.save()
    rising(watched, 3)
    # Any rise at all is enough: the plug is doing its job.
    assert drift_of(humidifier) is None


# --- What cannot be judged ---

def test_a_plug_assigned_to_no_plant_is_not_judged(actionner, watched):
    assert actionner.plant is None
    assert drift_of(actionner) is None


def test_a_plant_without_a_reading_is_not_judged(humidifier):
    assert drift_of(humidifier) is None


def test_one_reading_alone_is_not_enough(humidifier, watched):
    measure(watched, 80)
    assert drift_of(humidifier) is None


def test_two_readings_too_close_together_are_not_compared(humidifier, watched):
    # Three minutes apart: the plug has not had the time it is judged on.
    measure(watched, 50, minutes_ago=3)
    measure(watched, 90)
    assert drift_of(humidifier) is None


def test_readings_that_stopped_coming_are_not_judged(humidifier, watched):
    humidifier.is_on = True
    humidifier.save()
    measure(watched, 50, minutes_ago=60)
    measure(watched, 50, minutes_ago=40)
    # A sensor that stopped talking is not a plug that stopped working.
    assert drift_of(humidifier) is None


def test_a_measure_the_sensors_do_not_report_is_not_judged(growing_plant, watched, db):
    mat = Actionner.objects.create(name="Tapis chauffant", act_on="temperature",
                                   plant=growing_plant, mqtt_topic_out="jardin/tapis/set")
    rising(watched, 20)
    # The humidity climbed, but nothing says anything about the temperature.
    assert drift_of(mat) is None


def test_the_measure_is_read_with_the_keys_of_its_sensor(humidifier, watched):
    watched.humidity_payload_label = "hum"
    watched.save()
    measure(watched, 50, minutes_ago=6, label="hum")
    measure(watched, 70, label="hum")
    assert drift_of(humidifier) is not None


def test_a_sensor_naming_its_measure_otherwise_is_not_read_by_the_usual_key(humidifier, watched):
    watched.humidity_payload_label = "hum"
    watched.save()
    measure(watched, 50, minutes_ago=6)
    measure(watched, 70)
    # Written under "humidity", which this sensor does not use: nothing to judge on.
    assert drift_of(humidifier) is None


def test_a_reading_that_carries_nothing_is_skipped(humidifier, watched):
    measure(watched, 50, minutes_ago=6)
    measure(watched, 70)
    # A payload with no humidity in it does not hide the one behind it.
    SensorData.objects.create(sensor=watched, plant=watched.plant, payload='{"temperature": 21}')
    assert drift_of(humidifier) is not None


# --- The pass over every plug ---

def test_the_pass_warns_about_the_plugs_that_are_belied(humidifier, watched):
    rising(watched, 20)
    assert check_the_actionners() == {'checked': 1, 'warned': 1}
    warning = feedback.standing()[0]
    assert warning['name'] == "Brumisateur"
    assert warning['kind'] == feedback.KIND_EFFECT


def test_the_pass_leaves_the_plugs_that_add_up_alone(humidifier, watched):
    rising(watched, 1)
    assert check_the_actionners() == {'checked': 1, 'warned': 0}
    assert feedback.standing() == []


def test_a_plug_of_no_plant_is_not_even_looked_at(actionner, humidifier, watched):
    rising(watched, 20)
    assert check_the_actionners()['checked'] == 1


def test_a_deleted_plug_is_not_looked_at(humidifier, watched):
    humidifier.is_deleted = True
    humidifier.save()
    rising(watched, 20)
    assert check_the_actionners() == {'checked': 0, 'warned': 0}


def test_nothing_is_switched_by_the_check(humidifier, watched):
    rising(watched, 20)
    check_the_actionners()
    humidifier.refresh_from_db()
    # What the plugs do is the user's business: the worker only says so.
    assert not humidifier.is_on


def test_the_warning_is_written_in_the_journal_once(humidifier, watched):
    rising(watched, 20)
    check_the_actionners()
    check_the_actionners()
    written = AppLog.objects.get(type="WARNING")
    assert "Brumisateur" in written.message
    assert "est éteint, mais l'humidité monte quand même" in written.message


def test_the_warning_stands_beside_the_one_about_the_state(humidifier, watched):
    rising(watched, 20)
    check_the_actionners()
    feedback.warn(humidifier, feedback.KIND_STATE, "se dit allumé")
    # Two ways of belying the application, two warnings to settle.
    assert {warning['kind'] for warning in feedback.standing()} == {feedback.KIND_STATE,
                                                                    feedback.KIND_EFFECT}


def test_settling_one_kind_leaves_the_other(client, humidifier, watched):
    rising(watched, 20)
    check_the_actionners()
    feedback.warn(humidifier, feedback.KIND_STATE, "se dit allumé")
    client.post(reverse("dismiss_actionner_warning",
                        kwargs={"actionner_id": humidifier.pk, "kind": feedback.KIND_STATE}))
    assert [warning['kind'] for warning in feedback.standing()] == [feedback.KIND_EFFECT]


def test_the_warning_shows_on_the_main_page(client, humidifier, watched):
    rising(watched, 20)
    check_the_actionners()
    content = client.get(reverse("growing_plants")).content.decode()
    assert "Brumisateur" in content
    assert "monte quand même" in content


# --- The scheduled task ---

def test_the_task_checks_the_plugs(humidifier, watched):
    rising(watched, 20)
    assert tasks.check_the_plugs() == {'checked': 1, 'warned': 1}
