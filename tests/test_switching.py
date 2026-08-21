"""Telling the plugs the state the application says they should be in."""
import json

import pytest

from mqtt_worker import switching, tasks
from plant_management.models import Actionner, AppLog


@pytest.fixture
def sent(monkeypatch):
    """Catches what would go on the broker, without a broker."""
    calls = []

    def remember(messages, **options):
        calls.append({'messages': messages, 'options': options})

    monkeypatch.setattr(switching.mqtt_publish, 'multiple', remember)
    return calls


# --- What is sent ---

def test_an_actionner_switched_on_is_told_to_turn_on(actionner):
    actionner.is_on = True
    actionner.save()
    assert switching.orders() == [{
        'topic': "bonjour-plant/balcon/lampe/set",
        'payload': json.dumps({'state': "ON"}),
    }]


def test_an_actionner_switched_off_is_told_to_turn_off(actionner):
    assert not actionner.is_on
    assert json.loads(switching.orders()[0]['payload']) == {'state': "OFF"}


def test_a_deleted_actionner_is_not_told_anything(actionner):
    actionner.is_deleted = True
    actionner.save()
    assert switching.orders() == []


def test_an_actionner_without_a_topic_is_not_told_anything(actionner):
    actionner.mqtt_topic = ""
    actionner.save()
    assert switching.orders() == []


def test_every_actionner_gets_its_own_order(actionner, db):
    Actionner.objects.create(name="Brumisateur", act_on="humidity",
                             mqtt_topic="bonjour-plant/serre/brumisateur/set", is_on=True)
    orders = switching.orders()
    assert len(orders) == 2
    assert {order['topic'] for order in orders} == {
        "bonjour-plant/balcon/lampe/set", "bonjour-plant/serre/brumisateur/set"}


# --- How it is sent ---

def test_the_orders_go_to_the_broker(actionner, sent):
    assert switching.send_orders() == 1
    assert len(sent) == 1
    assert sent[0]['messages'] == switching.orders()
    assert sent[0]['options']['hostname'] == "localhost"
    assert sent[0]['options']['port'] == 1883


def test_nothing_is_sent_when_there_is_nothing_to_say(db, sent):
    assert switching.send_orders() == 0
    assert sent == []


def test_the_credentials_of_the_broker_are_used(actionner, sent, settings):
    settings.MQTT_BROKER_URL = "mqtts://prise:secret@broker.local:8884"
    switching.send_orders()
    options = sent[0]['options']
    assert (options['hostname'], options['port']) == ("broker.local", 8884)
    assert options['auth'] == {'username': "prise", 'password': "secret"}
    assert options['tls'] == {}


def test_a_plain_broker_is_reached_without_credentials(actionner, sent):
    switching.send_orders()
    assert sent[0]['options']['auth'] is None
    assert sent[0]['options']['tls'] is None


def test_two_runs_do_not_share_a_client_name(actionner, sent):
    switching.send_orders()
    switching.send_orders()
    assert sent[0]['options']['client_id'] != sent[1]['options']['client_id']


# --- The scheduled task ---

def test_the_task_sends_the_orders(actionner, sent):
    assert tasks.switch_the_plugs() == 1
    assert len(sent) == 1


def test_the_task_reports_a_broker_it_cannot_reach(actionner, monkeypatch, db):
    def refuse(messages, **options):
        raise OSError("connexion refusée")

    monkeypatch.setattr(switching.mqtt_publish, 'multiple', refuse)
    # Answers rather than raising: the next pass is a minute away.
    assert tasks.switch_the_plugs() == 0
    assert AppLog.objects.filter(type="ERROR", message__contains="pas pu être commandées").count() == 1


def test_the_state_sent_follows_the_database(actionner, sent):
    tasks.switch_the_plugs()
    assert json.loads(sent[0]['messages'][0]['payload']) == {'state': "OFF"}

    actionner.is_on = True
    actionner.save()
    tasks.switch_the_plugs()
    assert json.loads(sent[1]['messages'][0]['payload']) == {'state': "ON"}


# --- What the journal keeps of it ---

def test_the_instruction_sent_is_written_in_the_journal(actionner, sent):
    switching.send_orders()
    written = AppLog.objects.get(type="INFO")
    assert "Instruction MQTT envoyée" in written.message
    assert "Lampe UV du balcon" in written.message
    assert "OFF" in written.message
    assert "bonjour-plant/balcon/lampe/set" in written.message


def test_the_same_instruction_repeated_is_written_once(actionner, sent):
    switching.send_orders()
    switching.send_orders()
    switching.send_orders()
    # The order goes out every pass, the journal keeps the instruction once.
    assert len(sent) == 3
    assert AppLog.objects.filter(message__contains="Instruction MQTT").count() == 1


def test_a_change_of_instruction_is_written_again(actionner, sent):
    switching.send_orders()
    actionner.is_on = True
    actionner.save()
    switching.send_orders()
    written = AppLog.objects.filter(message__contains="Instruction MQTT").order_by('id')
    assert [("OFF" in log.message, "ON" in log.message) for log in written] == [(True, False), (False, True)]


def test_nothing_is_written_when_the_broker_refused(actionner, monkeypatch, db):
    def refuse(messages, **options):
        raise OSError("connexion refusée")

    monkeypatch.setattr(switching.mqtt_publish, 'multiple', refuse)
    tasks.switch_the_plugs()
    # Only the failure is worth a line: no order actually went out.
    assert not AppLog.objects.filter(message__contains="Instruction MQTT").exists()
    assert AppLog.objects.filter(type="ERROR").count() == 1
