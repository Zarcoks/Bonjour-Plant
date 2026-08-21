"""The actionners: connected plugs playing on one factor of a plant."""
import datetime

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from plant_management.models import Actionner, AppLog


def test_actionners_page(client, actionner):
    response = client.get(reverse("actionners"))
    assert response.status_code == 200
    content = response.content.decode()
    # The card shows the name, what it acts on, its state and its assignment.
    assert "Lampe UV du balcon" in content
    assert "lumière" in content
    assert "Éteint" in content
    assert "Assigné à aucune plante" in content
    assert "Jamais basculé" in content


def test_an_htmx_request_only_gets_the_grid(client, actionner):
    response = client.get(reverse("actionners"), headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert b"Lampe UV du balcon" in response.content
    # No layout: the answer replaces the grid alone.
    assert b"<html" not in response.content


def test_detail_returns_the_edition_form(client, actionner):
    response = client.get(reverse("actionner_detail", kwargs={"actionner_id": actionner.pk}))
    assert response.status_code == 200
    content = response.content.decode()
    for field in ['name="name"', 'name="act_on"', 'name="mqtt_topic_out"', 'name="mqtt_topic_in"',
                  'name="state_payload_label"', 'name="plant"', 'name="is_on"', 'name="photo"']:
        assert field in content
    assert "Valider" in content and "Annuler" in content and "Supprimer" in content


def test_card_returns_the_collapsed_card(client, actionner):
    response = client.get(reverse("actionner_card", kwargs={"actionner_id": actionner.pk}))
    assert response.status_code == 200
    assert b'name="mqtt_topic_out"' not in response.content


def test_update(client, actionner, actionner_payload):
    response = client.post(reverse("actionner_detail", kwargs={"actionner_id": actionner.pk}),
                           actionner_payload)
    assert response.status_code == 200
    actionner.refresh_from_db()
    assert actionner.name == "Humidificateur de la serre"
    assert actionner.act_on == "humidity"
    assert b'name="mqtt_topic_out"' not in response.content
    assert AppLog.objects.filter(type="INFO", message__contains="a été modifié").count() == 1


def test_update_without_a_topic_sends_the_form_back(client, actionner, actionner_payload):
    actionner_payload['mqtt_topic_out'] = ""
    response = client.post(reverse("actionner_detail", kwargs={"actionner_id": actionner.pk}),
                           actionner_payload)
    assert response.status_code == 200
    actionner.refresh_from_db()
    assert actionner.name == "Lampe UV du balcon"
    assert b'name="mqtt_topic_out"' in response.content
    assert AppLog.objects.filter(type="WARNING").count() == 1


def test_what_it_acts_on_is_one_of_the_measures(client, actionner, actionner_payload):
    actionner_payload['act_on'] = "la lune"
    response = client.post(reverse("actionner_detail", kwargs={"actionner_id": actionner.pk}),
                           actionner_payload)
    actionner.refresh_from_db()
    assert actionner.act_on == "luminosity"
    assert b'name="act_on"' in response.content


# --- Switching it on and off ---

def test_switching_it_on_notes_the_moment(client, actionner, actionner_payload):
    assert actionner.last_switch is None
    client.post(reverse("actionner_detail", kwargs={"actionner_id": actionner.pk}),
                dict(actionner_payload, is_on="on"))
    actionner.refresh_from_db()
    assert actionner.is_on
    assert actionner.last_switch.date() == timezone.now().date()
    assert AppLog.objects.filter(type="INFO", message__contains="veut allumer").count() == 1


def test_switching_it_off_notes_the_moment_too(client, actionner, actionner_payload):
    actionner.is_on = True
    actionner.last_switch = timezone.now() - datetime.timedelta(days=2)
    actionner.save()
    switched_before = actionner.last_switch
    client.post(reverse("actionner_detail", kwargs={"actionner_id": actionner.pk}), actionner_payload)
    actionner.refresh_from_db()
    assert not actionner.is_on
    assert actionner.last_switch > switched_before
    assert AppLog.objects.filter(type="INFO", message__contains="veut éteindre").count() == 1


def test_a_change_that_is_not_a_switch_leaves_the_moment_alone(client, actionner, actionner_payload):
    actionner.last_switch = timezone.now() - datetime.timedelta(days=2)
    actionner.save()
    untouched = actionner.last_switch
    client.post(reverse("actionner_detail", kwargs={"actionner_id": actionner.pk}), actionner_payload)
    actionner.refresh_from_db()
    assert actionner.last_switch == untouched


# --- Assignment ---

def test_it_is_assigned_to_a_plant(client, actionner, growing_plant, actionner_payload):
    actionner_payload['plant'] = growing_plant.pk
    response = client.post(reverse("actionner_detail", kwargs={"actionner_id": actionner.pk}),
                           actionner_payload)
    actionner.refresh_from_db()
    assert actionner.plant == growing_plant
    assert "Basilic du balcon" in response.content.decode()


def test_it_is_assigned_back_to_nothing(client, actionner, growing_plant, actionner_payload):
    actionner.plant = growing_plant
    actionner.save()
    response = client.post(reverse("actionner_detail", kwargs={"actionner_id": actionner.pk}),
                           actionner_payload)
    actionner.refresh_from_db()
    assert actionner.plant is None
    assert "Assigné à aucune plante" in response.content.decode()


def test_a_deleted_plant_is_not_offered(client, actionner, growing_plant):
    growing_plant.is_deleted = True
    growing_plant.save()
    content = client.get(reverse("actionner_detail", kwargs={"actionner_id": actionner.pk})).content.decode()
    assert "Basilic du balcon" not in content


def test_deleting_a_plant_frees_its_actionners(client, actionner, growing_plant):
    actionner.plant = growing_plant
    actionner.save()
    client.post(reverse("delete_growing_plant", kwargs={"plant_id": growing_plant.pk}))
    actionner.refresh_from_db()
    assert actionner.plant is None


# --- Creation ---

def test_create_form(client, db):
    response = client.get(reverse("create_actionner"))
    assert response.status_code == 200
    assert b'name="mqtt_topic_out"' in response.content


def test_create(client, db, actionner_payload):
    response = client.post(reverse("create_actionner"), actionner_payload)
    assert response.status_code == 200
    created = Actionner.objects.get(name="Humidificateur de la serre")
    assert created.act_on == "humidity"
    assert not created.is_on and created.plant is None
    # No photo given: the default illustration is used.
    assert "actionner-default.svg" in created.get_photo_url()
    assert b'hx-swap-oob' in response.content
    assert AppLog.objects.filter(type="INFO", message__contains="a été créé").count() == 1


def test_create_switched_on_notes_the_moment(client, db, actionner_payload):
    client.post(reverse("create_actionner"), dict(actionner_payload, is_on="on"))
    created = Actionner.objects.get(name="Humidificateur de la serre")
    assert created.is_on
    assert created.last_switch is not None


def test_create_with_invalid_input_is_retargeted_to_the_form(client, db, actionner_payload):
    del actionner_payload['name']
    response = client.post(reverse("create_actionner"), actionner_payload)
    assert response.status_code == 200
    assert not Actionner.objects.exists()
    assert response['HX-Retarget'] == '#actionner-create'
    assert response['HX-Reswap'] == 'innerHTML'


def test_create_with_a_photo(client, db, actionner_payload, settings, tmp_path, png_bytes):
    settings.MEDIA_ROOT = tmp_path
    photo = SimpleUploadedFile("prise.png", png_bytes, content_type="image/png")
    response = client.post(reverse("create_actionner"), dict(actionner_payload, photo=photo))
    created = Actionner.objects.get(name="Humidificateur de la serre")
    assert created.photo.name.startswith("actionners/prise")
    assert created.photo.url in response.content.decode()


# --- Deletion ---

def test_delete_flags_it_and_asks_the_page_to_reload_its_grid(client, actionner):
    response = client.post(reverse("delete_actionner", kwargs={"actionner_id": actionner.pk}))
    assert response.status_code == 204
    assert response['HX-Trigger'] == 'refresh-actionners'
    actionner.refresh_from_db()
    # The row stays, flagged as deleted, and leaves the grid.
    assert actionner.is_deleted
    assert b"Lampe UV du balcon" not in client.get(reverse("actionners")).content
    assert AppLog.objects.filter(type="INFO", message__contains="a été supprimé").count() == 1


def test_an_actionner_cannot_be_deleted_twice(client, actionner):
    url = reverse("delete_actionner", kwargs={"actionner_id": actionner.pk})
    assert client.post(url).status_code == 204
    assert client.post(url).status_code == 404


def test_a_deleted_actionner_is_never_listed(client, actionner):
    actionner.is_deleted = True
    actionner.save()
    assert b"Lampe UV du balcon" not in client.get(reverse("actionners")).content


def test_a_deleted_actionner_cannot_be_reached(client, actionner):
    actionner.is_deleted = True
    actionner.save()
    for name in ["actionner_detail", "actionner_card"]:
        assert client.get(reverse(name, kwargs={"actionner_id": actionner.pk})).status_code == 404


# --- Switching a light off by hand takes the plant over ---

@pytest.fixture
def lamp_of(growing_plant, db):
    """A lamp, lit, on a plant whose light is left to the application."""
    growing_plant.auto_luminosity = True
    growing_plant.save()
    return Actionner.objects.create(name="Lampe UV", act_on="luminosity", plant=growing_plant,
                                    mqtt_topic_out="bonjour-plant/balcon/lampe/set", is_on=True)


def payload_of(actionner, **changes):
    """What the form sends back for that actionner, unchanged unless said otherwise."""
    fields = {
        'name': actionner.name,
        'act_on': actionner.act_on,
        'mqtt_topic_out': actionner.mqtt_topic_out,
        'mqtt_topic_in': actionner.mqtt_topic_in,
        'state_payload_label': actionner.state_payload_label,
        'plant': actionner.plant.pk if actionner.plant else "",
    }
    return dict(fields, **changes)


def switch(client, actionner, **changes):
    return client.post(reverse("actionner_detail", kwargs={"actionner_id": actionner.pk}),
                       payload_of(actionner, **changes))


def test_switching_a_light_off_stops_the_automatic_light(client, lamp_of, growing_plant):
    switch(client, lamp_of)          # the box left unticked switches it off
    growing_plant.refresh_from_db()
    assert not growing_plant.auto_luminosity
    assert AppLog.objects.filter(type="INFO",
                                 message__contains="lumière automatique de la plante").count() == 1


def test_switching_a_light_on_leaves_the_automatic_light_alone(client, lamp_of, growing_plant):
    lamp_of.is_on = False
    lamp_of.save()
    switch(client, lamp_of, is_on="on")
    growing_plant.refresh_from_db()
    # Only switching off hands the light back: switching on is not asked to.
    assert growing_plant.auto_luminosity


def test_switching_off_something_that_is_not_a_light_leaves_it_alone(client, growing_plant, db):
    growing_plant.auto_luminosity = True
    growing_plant.save()
    humidifier = Actionner.objects.create(name="Brumisateur", act_on="humidity", plant=growing_plant,
                                          mqtt_topic_out="bonjour-plant/serre/brumisateur/set", is_on=True)
    switch(client, humidifier)
    growing_plant.refresh_from_db()
    assert growing_plant.auto_luminosity


def test_a_light_of_no_plant_hands_nothing_back(client, actionner):
    actionner.is_on = True
    actionner.save()
    assert actionner.plant is None
    switch(client, actionner)
    actionner.refresh_from_db()
    assert not actionner.is_on


def test_a_plant_already_on_manual_light_is_not_written_again(client, lamp_of, growing_plant):
    growing_plant.auto_luminosity = False
    growing_plant.save()
    switch(client, lamp_of)
    assert not AppLog.objects.filter(message__contains="lumière automatique de la plante").exists()


def test_a_change_that_is_not_a_switch_leaves_the_automatic_light_alone(client, lamp_of, growing_plant):
    switch(client, lamp_of, name="Lampe UV du balcon", is_on="on")
    growing_plant.refresh_from_db()
    assert growing_plant.auto_luminosity


# --- Switching a pump by hand takes the plant over ---

@pytest.fixture
def pump_of(growing_plant, db):
    """A pump, running, on a plant whose watering is left to the application."""
    growing_plant.auto_watering = True
    growing_plant.save()
    return Actionner.objects.create(name="Pompe", act_on="humidity", plant=growing_plant,
                                    mqtt_topic_out="bonjour-plant/balcon/pompe/set", is_on=True)


def test_switching_a_pump_off_stops_the_automatic_watering(client, pump_of, growing_plant):
    switch(client, pump_of)          # the box left unticked switches it off
    growing_plant.refresh_from_db()
    assert not growing_plant.auto_watering
    assert AppLog.objects.filter(type="INFO",
                                 message__contains="arrosage automatique de la plante").count() == 1


def test_switching_a_pump_on_stops_the_automatic_watering_too(client, pump_of, growing_plant):
    pump_of.is_on = False
    pump_of.save()
    switch(client, pump_of, is_on="on")
    growing_plant.refresh_from_db()
    # Touching the switch either way is taking the water of the plant over.
    assert not growing_plant.auto_watering


def test_switching_something_that_is_not_a_pump_leaves_the_watering_alone(client, lamp_of, growing_plant):
    growing_plant.auto_watering = True
    growing_plant.save()
    switch(client, lamp_of)
    growing_plant.refresh_from_db()
    assert growing_plant.auto_watering


def test_a_pump_of_no_plant_hands_nothing_back(client, actionner):
    actionner.act_on = "humidity"
    actionner.is_on = True
    actionner.save()
    assert actionner.plant is None
    switch(client, actionner)
    actionner.refresh_from_db()
    assert not actionner.is_on


def test_a_plant_already_watered_by_hand_is_not_written_again(client, pump_of, growing_plant):
    growing_plant.auto_watering = False
    growing_plant.save()
    switch(client, pump_of)
    assert not AppLog.objects.filter(message__contains="arrosage automatique de la plante").exists()


def test_a_change_that_is_not_a_switch_leaves_the_automatic_watering_alone(client, pump_of, growing_plant):
    switch(client, pump_of, name="Pompe du balcon", is_on="on")
    growing_plant.refresh_from_db()
    assert growing_plant.auto_watering
