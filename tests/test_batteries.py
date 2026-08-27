"""The batteries of the sensors, and the warnings they raise."""
from django.urls import reverse

from battery_worker import check_the_batteries, tasks
from mqtt_worker import feedback
from plant_management.models import AppLog, Sensor


def dismiss_url(sensor, kind=feedback.KIND_BATTERY):
    return reverse("dismiss_warning", kwargs={"subject": "sensor", "device_id": sensor.pk,
                                              "kind": kind})


def test_a_sensor_running_out_of_batteries_is_warned_about(sensor):
    sensor.battery_level = 7
    sensor.save()
    assert check_the_batteries() == {'checked': 1, 'warned': 1}
    warning = feedback.standing()[0]
    assert warning['name'] == "Sonde d'humidité du balcon"
    assert warning['kind'] == feedback.KIND_BATTERY
    assert warning['message'] == "n'a plus que 7 % de batterie : il est temps de changer ses piles"


def test_a_sensor_with_batteries_left_is_left_alone(sensor):
    sensor.battery_level = 64
    sensor.save()
    assert check_the_batteries() == {'checked': 1, 'warned': 0}
    assert feedback.standing() == []


def test_a_sensor_that_said_nothing_of_its_batteries_is_not_even_looked_at(sensor):
    assert sensor.battery_level is None
    # Silence is not an empty battery: there is nothing to judge.
    assert check_the_batteries() == {'checked': 0, 'warned': 0}


def test_a_deleted_sensor_is_not_looked_at(sensor):
    sensor.battery_level = 3
    sensor.is_deleted = True
    sensor.save()
    assert check_the_batteries() == {'checked': 0, 'warned': 0}


def test_a_sensor_of_no_plant_is_warned_about_all_the_same(sensor):
    assert sensor.plant is None
    sensor.battery_level = 2
    sensor.save()
    # Its batteries are its own business, whatever it watches.
    assert check_the_batteries() == {'checked': 1, 'warned': 1}


def test_nothing_is_changed_on_the_sensor_by_the_check(sensor):
    sensor.battery_level = 5
    sensor.save()
    check_the_batteries()
    sensor.refresh_from_db()
    # Changing the batteries is the user's business: the worker only says so.
    assert sensor.battery_level == 5


def test_the_low_battery_is_written_in_the_journal_once(sensor):
    sensor.battery_level = 4
    sensor.save()
    check_the_batteries()
    check_the_batteries()
    written = AppLog.objects.get(type="WARNING")
    assert "Le capteur Sonde d'humidité du balcon" in written.message
    assert "changer ses piles" in written.message


def test_the_low_battery_shows_on_the_main_page(client, sensor):
    sensor.battery_level = 6
    sensor.save()
    check_the_batteries()
    content = client.get(reverse("growing_plants")).content.decode()
    assert "changer ses piles" in content
    assert "C'est réglé" in content


def test_the_user_settles_a_low_battery(client, sensor):
    sensor.battery_level = 6
    sensor.save()
    check_the_batteries()
    response = client.post(dismiss_url(sensor))
    assert response.status_code == 200
    assert feedback.standing() == []
    assert AppLog.objects.filter(type="INFO", message__contains="a été réglé").count() == 1


def test_the_low_battery_of_one_sensor_leaves_the_others(client, sensor):
    other = Sensor.objects.create(name="Luxmètre de la serre", model="Test",
                                  mqtt_topic="bonjour-plant/serre/lux", battery_level=8)
    sensor.battery_level = 6
    sensor.save()
    check_the_batteries()
    client.post(dismiss_url(sensor))
    assert [warning['name'] for warning in feedback.standing()] == [other.name]


def test_a_low_battery_stands_beside_what_a_plug_belies(client, sensor, actionner):
    sensor.battery_level = 5
    sensor.save()
    check_the_batteries()
    feedback.warn(actionner, feedback.KIND_STATE, "se dit allumé")
    # Two devices, two genres, the same banner: one warning to settle each.
    assert {warning['kind'] for warning in feedback.standing()} == {feedback.KIND_STATE,
                                                                   feedback.KIND_BATTERY}
    client.post(dismiss_url(sensor))
    assert [warning['kind'] for warning in feedback.standing()] == [feedback.KIND_STATE]


def test_deleting_a_sensor_settles_its_low_battery(client, sensor):
    sensor.battery_level = 6
    sensor.save()
    check_the_batteries()
    client.post(reverse("delete_sensor", kwargs={"sensor_id": sensor.pk}))
    assert feedback.standing() == []


def test_a_kind_a_sensor_is_never_warned_about_is_refused(client, sensor):
    assert client.post(dismiss_url(sensor, kind=feedback.KIND_STATE)).status_code == 404


def test_a_subject_that_is_not_warned_about_at_all_is_refused(client, sensor):
    assert client.post(reverse("dismiss_warning", kwargs={"subject": "plante",
                                                          "device_id": sensor.pk,
                                                          "kind": feedback.KIND_BATTERY})
                       ).status_code == 404


def test_the_task_checks_the_batteries(sensor):
    sensor.battery_level = 9
    sensor.save()
    assert tasks.check_the_batteries() == {'checked': 1, 'warned': 1}
