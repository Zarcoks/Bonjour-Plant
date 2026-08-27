"""What the plugs say of themselves, and the warnings that follow."""
import json

import pytest
from django.urls import reverse

from mqtt_worker import SensorListener, broker_from_url, feedback
from plant_management.models import Actionner, AppLog


@pytest.fixture
def listener():
    return SensorListener(broker=broker_from_url("mqtt://broker:1883"), sync_seconds=1)


@pytest.fixture
def plug(actionner):
    """A plug the application believes is off, reporting on a topic of its own."""
    assert not actionner.is_on
    assert actionner.mqtt_topic_in == "bonjour-plant/balcon/lampe"
    return actionner


def reports(plug, payload):
    """What the listener does with that payload arriving from that plug."""
    return feedback.check(plug.mqtt_topic_in, payload)


def says(state, label='state'):
    return json.dumps({label: state})


def dismiss_url(plug, kind=feedback.KIND_STATE):
    """Where « c'est réglé » is posted for that plug and that kind."""
    return reverse("dismiss_warning", kwargs={"subject": "actionner", "device_id": plug.pk,
                                              "kind": kind})


# --- Reading a state out of a payload ---

@pytest.mark.parametrize("value", ["ON", "on", " On ", True, 1, "true", "yes"])
def test_the_words_meaning_on_are_read(value):
    assert feedback.to_state(value) is True


@pytest.mark.parametrize("value", ["OFF", "off", False, 0, "false", "no"])
def test_the_words_meaning_off_are_read(value):
    assert feedback.to_state(value) is False


@pytest.mark.parametrize("value", ["banane", "", None, 7, [1]])
def test_anything_else_is_not_a_state(value):
    assert feedback.to_state(value) is None


def test_a_payload_is_read_with_the_key_of_its_plug(plug):
    assert feedback.reported_state(plug, says("ON")) is True
    assert feedback.reported_state(plug, says("OFF")) is False


def test_a_plug_naming_its_state_otherwise_is_read_with_its_own_key(plug):
    plug.state_payload_label = "power"
    plug.save()
    assert feedback.reported_state(plug, says("ON", label='power')) is True
    # The usual key means nothing to it any more.
    assert feedback.reported_state(plug, says("ON")) is None


def test_a_plug_with_no_key_of_its_own_falls_back_on_the_usual_one(plug):
    plug.state_payload_label = ""
    plug.save()
    assert feedback.reported_state(plug, says("ON")) is True


@pytest.mark.parametrize("payload", ["pas du json", "[]", "null", '{}', '{"state": "banane"}'])
def test_a_payload_carrying_no_state_reports_nothing(plug, payload):
    assert feedback.reported_state(plug, payload) is None


# --- What is warned about ---

def test_a_plug_reporting_what_it_was_asked_raises_nothing(plug):
    assert reports(plug, says("OFF")) == []
    assert feedback.standing() == []


def test_a_plug_reporting_otherwise_is_warned_about(plug):
    assert reports(plug, says("ON")) == [plug]
    warning = feedback.standing()[0]
    assert warning['name'] == "Lampe UV du balcon"
    assert warning['kind'] == feedback.KIND_STATE
    assert warning['message'] == "se dit allumé alors que l'application le veut éteint"


def test_the_disagreement_is_written_in_the_journal(plug):
    reports(plug, says("ON"))
    written = AppLog.objects.get(type="WARNING")
    assert "Lampe UV du balcon" in written.message
    assert "se dit allumé" in written.message


def test_the_same_disagreement_is_written_once(plug):
    for _ in range(3):
        reports(plug, says("ON"))
    # One line per plug that drifted, not one per message it sends.
    assert AppLog.objects.filter(type="WARNING").count() == 1
    assert len(feedback.standing()) == 1


def test_a_standing_warning_keeps_the_time_it_was_first_seen(plug):
    reports(plug, says("ON"))
    since = feedback.standing()[0]['since']
    reports(plug, says("ON"))
    refreshed = feedback.standing()[0]
    assert refreshed['since'] == since
    assert refreshed['at'] > since


def test_the_warning_stands_when_the_plug_falls_back_in_line(plug):
    reports(plug, says("ON"))
    reports(plug, says("OFF"))
    # Only the user settles a warning: a plug that drifted is worth knowing about.
    assert len(feedback.standing()) == 1


@pytest.mark.parametrize("payload", ["pas du json", '{}', '{"state": "banane"}'])
def test_a_payload_we_cannot_read_is_no_disagreement(plug, payload):
    assert reports(plug, payload) == []
    assert feedback.standing() == []


def test_a_message_on_another_topic_is_not_read(plug):
    assert feedback.check("bonjour-plant/serre/brumisateur", says("ON")) == []
    assert feedback.standing() == []


def test_a_plug_that_reports_nowhere_is_never_read(plug):
    plug.mqtt_topic_in = ""
    plug.save()
    assert feedback.check("", says("ON")) == []
    assert feedback.topics() == set()


def test_a_deleted_plug_is_not_read(plug):
    plug.is_deleted = True
    plug.save()
    assert reports(plug, says("ON")) == []


def test_a_deleted_plug_is_not_complained_about(plug):
    reports(plug, says("ON"))
    plug.is_deleted = True
    plug.save()
    assert feedback.standing() == []


def test_every_plug_listening_on_that_topic_is_read(plug, db):
    twin = Actionner.objects.create(name="Doublon", act_on="luminosity", is_on=True,
                                    mqtt_topic_out="bonjour-plant/balcon/lampe/set",
                                    mqtt_topic_in="bonjour-plant/balcon/lampe")
    # The plug is off for the application, the twin is on: the same "ON" belies
    # the first one only.
    assert reports(plug, says("ON")) == [plug]
    assert twin not in feedback.check(twin.mqtt_topic_in, says("ON"))


def test_disagreements_come_back_newest_first(plug, db):
    other = Actionner.objects.create(name="Brumisateur", act_on="humidity",
                                     mqtt_topic_out="bonjour-plant/serre/brumisateur/set",
                                     mqtt_topic_in="bonjour-plant/serre/brumisateur")
    reports(plug, says("ON"))
    feedback.check(other.mqtt_topic_in, says("ON"))
    assert [warning['name'] for warning in feedback.standing()] == ["Brumisateur",
                                                                        "Lampe UV du balcon"]


# --- What the listener listens to ---

def test_the_topics_carry_the_plugs_that_report(listener, plug, sensor):
    assert listener.topics() == {"bonjour-plant/balcon/humidity", "bonjour-plant/balcon/lampe"}


def test_a_message_is_read_for_the_plugs_too(listener, plug):
    listener.handle_message(plug.mqtt_topic_in, says("ON"))
    assert len(feedback.standing()) == 1


# --- The banner on the main page ---

def test_the_main_page_shows_nothing_without_a_disagreement(client, plug):
    content = client.get(reverse("growing_plants")).content.decode()
    assert 'id="installation-warnings"' in content
    assert "C'est réglé" not in content


def test_the_main_page_shows_the_disagreement(client, plug):
    reports(plug, says("ON"))
    content = client.get(reverse("growing_plants")).content.decode()
    assert "Lampe UV du balcon" in content
    assert "C'est réglé" in content


def test_the_banner_can_be_asked_for_on_its_own(client, plug):
    reports(plug, says("ON"))
    content = client.get(reverse("warnings")).content.decode()
    assert "Lampe UV du balcon" in content


def test_the_user_settles_a_warning(client, plug):
    reports(plug, says("ON"))
    response = client.post(dismiss_url(plug))
    assert response.status_code == 200
    assert feedback.standing() == []
    assert "C'est réglé" not in response.content.decode()
    assert AppLog.objects.filter(type="INFO", message__contains="a été réglé").count() == 1


def test_settling_one_warning_leaves_the_others(client, plug, db):
    other = Actionner.objects.create(name="Brumisateur", act_on="humidity",
                                     mqtt_topic_out="bonjour-plant/serre/brumisateur/set",
                                     mqtt_topic_in="bonjour-plant/serre/brumisateur")
    reports(plug, says("ON"))
    feedback.check(other.mqtt_topic_in, says("ON"))
    response = client.post(dismiss_url(plug))
    assert [warning['name'] for warning in feedback.standing()] == ["Brumisateur"]
    assert "Brumisateur" in response.content.decode()


def test_a_warning_settled_comes_back_when_the_plug_drifts_again(client, plug):
    reports(plug, says("ON"))
    client.post(dismiss_url(plug))
    reports(plug, says("ON"))
    assert len(feedback.standing()) == 1


def test_deleting_an_actionner_settles_its_warning(client, plug):
    reports(plug, says("ON"))
    client.post(reverse("delete_actionner", kwargs={"actionner_id": plug.pk}))
    assert feedback.standing() == []


def test_a_warning_of_a_deleted_actionner_cannot_be_settled(client, plug):
    plug.is_deleted = True
    plug.save()
    assert client.post(dismiss_url(plug)).status_code == 404


def test_a_kind_of_warning_that_does_not_exist_is_refused(client, plug):
    assert client.post(dismiss_url(plug, kind="banane")).status_code == 404
