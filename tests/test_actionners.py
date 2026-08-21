"""The actionners: connected plugs playing on one factor of a plant."""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
import datetime

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
    for field in ['name="name"', 'name="act_on"', 'name="mqtt_topic"', 'name="plant"',
                  'name="is_on"', 'name="photo"']:
        assert field in content
    assert "Valider" in content and "Annuler" in content and "Supprimer" in content


def test_card_returns_the_collapsed_card(client, actionner):
    response = client.get(reverse("actionner_card", kwargs={"actionner_id": actionner.pk}))
    assert response.status_code == 200
    assert b'name="mqtt_topic"' not in response.content


def test_update(client, actionner, actionner_payload):
    response = client.post(reverse("actionner_detail", kwargs={"actionner_id": actionner.pk}),
                           actionner_payload)
    assert response.status_code == 200
    actionner.refresh_from_db()
    assert actionner.name == "Humidificateur de la serre"
    assert actionner.act_on == "humidity"
    assert b'name="mqtt_topic"' not in response.content
    assert AppLog.objects.filter(type="INFO", message__contains="a été modifié").count() == 1


def test_update_without_a_topic_sends_the_form_back(client, actionner, actionner_payload):
    actionner_payload['mqtt_topic'] = ""
    response = client.post(reverse("actionner_detail", kwargs={"actionner_id": actionner.pk}),
                           actionner_payload)
    assert response.status_code == 200
    actionner.refresh_from_db()
    assert actionner.name == "Lampe UV du balcon"
    assert b'name="mqtt_topic"' in response.content
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
    assert b'name="mqtt_topic"' in response.content


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
