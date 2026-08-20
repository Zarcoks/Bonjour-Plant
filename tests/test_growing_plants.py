import datetime

from django.urls import reverse
from django.utils import timezone

from plant_management.models import WELL_LIT_LEVEL, AppLog, GrowingPlant


def test_main_page_lists_the_growing_plants(client, growing_plant):
    response = client.get(reverse("growing_plants"))
    assert response.status_code == 200
    content = response.content.decode()
    # Name, plant type, planting date and growing state are all on the card.
    assert "Basilic du balcon" in content
    assert "Basilic" in content
    assert "Planté le" in content
    assert "70 %" in content


def test_deleted_plants_are_never_shown(client, growing_plant):
    growing_plant.is_deleted = True
    growing_plant.save()
    assert b"Basilic du balcon" not in client.get(reverse("growing_plants")).content


def test_harvested_plants_are_hidden_by_default(client, growing_plant, harvested_plant):
    content = client.get(reverse("growing_plants")).content.decode()
    assert "Basilic du balcon" in content
    assert "Laitue d'hiver" not in content


def test_harvested_plants_are_shown_on_demand(client, growing_plant, harvested_plant):
    content = client.get(reverse("growing_plants"), {'harvested': "1"}).content.decode()
    assert "Basilic du balcon" in content
    assert "Laitue d&#x27;hiver" in content
    assert "Récoltée" in content


def test_an_htmx_request_only_gets_the_list(client, growing_plant):
    response = client.get(reverse("growing_plants"), headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert b"growing-card" in response.content
    # No layout: the answer is a fragment, meant to replace the list alone.
    assert b"<html" not in response.content


def test_detail_returns_the_edition_form(client, growing_plant):
    response = client.get(reverse("growing_plant_detail", kwargs={"plant_id": growing_plant.pk}))
    assert response.status_code == 200
    content = response.content.decode()
    for field in ['name="display_name"', 'name="plant_type"', 'name="planted_date"', 'name="harvested"']:
        assert field in content
    assert "Valider" in content and "Annuler" in content


def test_card_returns_the_read_only_card(client, growing_plant):
    response = client.get(reverse("growing_plant_card", kwargs={"plant_id": growing_plant.pk}))
    assert response.status_code == 200
    assert b'name="display_name"' not in response.content


def test_the_plants_are_sorted_by_planting_date_with_the_harvested_ones_last(client, plant_type,
                                                                             growing_plant, harvested_plant):
    late = GrowingPlant.objects.create(display_name="Menthe tardive", plant_type=plant_type,
                                       planted_date=datetime.datetime(2026, 8, 7, 9, 0))
    early = GrowingPlant.objects.create(display_name="Fraisier hâtif", plant_type=plant_type,
                                        planted_date=datetime.datetime(2026, 6, 15, 9, 0))
    content = client.get(reverse("growing_plants"), {'harvested': "1"}).content.decode()
    positions = [content.index(name) for name in
                 [early.display_name, growing_plant.display_name, late.display_name]]
    assert positions == sorted(positions)
    # The harvested plant closes the list, whatever its planting date.
    assert content.index("Laitue") > max(positions)


def test_a_plant_without_a_planting_date_comes_last_among_the_growing_ones(client, plant_type, growing_plant):
    undated = GrowingPlant.objects.create(display_name="Bouture sans date", plant_type=plant_type)
    content = client.get(reverse("growing_plants")).content.decode()
    assert content.index(undated.display_name) > content.index(growing_plant.display_name)


# --- A harvested plant keeps its name, photo, planting date and growing bar ---

def test_a_harvested_card_is_stripped_down(client, harvested_plant):
    content = client.get(reverse("growing_plants"), {'harvested': "1"}).content.decode()
    assert "harvested-note" in content and "Récoltée" in content
    assert "le 2 août 2026" in content
    # Kept: name, photo, planting date, growing bar.
    assert "Laitue d&#x27;hiver" in content
    assert "growing-progress-bar" in content
    assert "Planté le 15 mai 2026" in content
    # Dropped: signs, automatic light, watering, plant type.
    assert "plant-sign" not in content
    assert "light-btn" not in content
    assert "Dernier arrosage" not in content
    assert "growing-card-type" not in content


def test_a_harvested_plant_without_a_harvest_day_only_shows_the_note(client, harvested_plant):
    harvested_plant.harvest_day = None
    harvested_plant.save()
    content = client.get(reverse("growing_plants"), {'harvested': "1"}).content.decode()
    assert "harvested-note" in content
    assert "harvested-day" not in content


def test_harvesting_a_plant_notes_the_day(client, growing_plant, plant_type):
    response = client.post(reverse("growing_plant_detail", kwargs={"plant_id": growing_plant.pk}), {
        'display_name': growing_plant.display_name,
        'plant_type': plant_type.pk,
        'planted_date': "2026-07-08",
        'harvested': "on",
    })
    assert response.status_code == 200
    growing_plant.refresh_from_db()
    # No day given: today is noted.
    assert growing_plant.harvest_day.date() == timezone.now().date()


def test_the_harvest_day_can_be_chosen(client, growing_plant, plant_type):
    client.post(reverse("growing_plant_detail", kwargs={"plant_id": growing_plant.pk}), {
        'display_name': growing_plant.display_name,
        'plant_type': plant_type.pk,
        'planted_date': "2026-07-08",
        'harvested': "on",
        'harvest_day': "2026-08-02",
    })
    growing_plant.refresh_from_db()
    assert growing_plant.harvest_day.strftime("%Y-%m-%d") == "2026-08-02"


def test_unharvesting_a_plant_clears_the_harvest_day(client, harvested_plant, plant_type):
    client.post(reverse("growing_plant_detail", kwargs={"plant_id": harvested_plant.pk}), {
        'display_name': harvested_plant.display_name,
        'plant_type': plant_type.pk,
        'harvest_day': "2026-08-02",
    })
    harvested_plant.refresh_from_db()
    assert not harvested_plant.harvested
    assert harvested_plant.harvest_day is None


# --- Creation ---

def test_create_form(client, db):
    response = client.get(reverse("create_growing_plant"))
    assert response.status_code == 200
    content = response.content.decode()
    for field in ['name="display_name"', 'name="plant_type"', 'name="planted_date"']:
        assert field in content
    # A plant is not harvested at creation time.
    assert 'name="harvested"' not in content


def test_create(client, db, growing_plant_payload):
    response = client.post(reverse("create_growing_plant"), growing_plant_payload)
    assert response.status_code == 200
    created = GrowingPlant.objects.get(display_name="Basilic de la fenêtre")
    assert created.planted_date.strftime("%Y-%m-%d") == "2026-03-12"
    assert not created.harvested and not created.is_deleted
    # The answer is the whole list, plus the out of band closing of the form.
    assert "Basilic de la fenêtre" in response.content.decode()
    assert b'hx-swap-oob' in response.content
    assert AppLog.objects.filter(type="INFO", message__contains="a été plantée").count() == 1


def test_create_keeps_the_harvested_filter(client, harvested_plant, growing_plant_payload):
    plain = client.post(reverse("create_growing_plant"), growing_plant_payload)
    assert "Laitue d&#x27;hiver" not in plain.content.decode()

    GrowingPlant.objects.filter(display_name="Basilic de la fenêtre").delete()
    with_harvested = client.post(reverse("create_growing_plant"), dict(growing_plant_payload, harvested="1"))
    assert "Laitue d&#x27;hiver" in with_harvested.content.decode()


def test_create_without_a_name_is_retargeted_to_the_form(client, db, growing_plant_payload):
    del growing_plant_payload['display_name']
    response = client.post(reverse("create_growing_plant"), growing_plant_payload)
    assert response.status_code == 200
    assert not GrowingPlant.objects.exists()
    assert response['HX-Retarget'] == '#growing-plant-create'
    assert response['HX-Reswap'] == 'innerHTML'
    assert AppLog.objects.filter(type="WARNING").count() == 1


# --- Deletion ---

def test_delete_flags_the_plant_and_asks_the_page_to_reload_its_list(client, growing_plant):
    response = client.post(reverse("delete_growing_plant", kwargs={"plant_id": growing_plant.pk}))
    assert response.status_code == 204
    assert response['HX-Trigger'] == 'refresh-plants'
    growing_plant.refresh_from_db()
    # The row stays, flagged as deleted, and leaves the list.
    assert growing_plant.is_deleted
    assert b"Basilic du balcon" not in client.get(reverse("growing_plants")).content
    assert AppLog.objects.filter(type="INFO", message__contains="a été supprimée").count() == 1


def test_a_plant_cannot_be_deleted_twice(client, growing_plant):
    url = reverse("delete_growing_plant", kwargs={"plant_id": growing_plant.pk})
    assert client.post(url).status_code == 204
    assert client.post(url).status_code == 404


def test_update(client, growing_plant, plant_type):
    response = client.post(reverse("growing_plant_detail", kwargs={"plant_id": growing_plant.pk}), {
        'display_name': "Basilic de la fenêtre",
        'plant_type': plant_type.pk,
        'planted_date': "2026-03-12",
        'harvested': "on",
    })
    assert response.status_code == 200
    growing_plant.refresh_from_db()
    assert growing_plant.display_name == "Basilic de la fenêtre"
    assert growing_plant.planted_date.strftime("%Y-%m-%d") == "2026-03-12"
    assert growing_plant.harvested
    # The answer is the read only card, and both the change and the harvest are logged.
    assert b'name="display_name"' not in response.content
    assert AppLog.objects.filter(type="INFO", message__contains="a été modifiée").count() == 1
    assert AppLog.objects.filter(type="INFO", message__contains="a été récoltée").count() == 1


def test_update_without_a_name_sends_the_form_back(client, growing_plant, plant_type):
    response = client.post(reverse("growing_plant_detail", kwargs={"plant_id": growing_plant.pk}),
                           {'display_name': "", 'plant_type': plant_type.pk})
    assert response.status_code == 200
    growing_plant.refresh_from_db()
    assert growing_plant.display_name == "Basilic du balcon"
    assert b'name="display_name"' in response.content
    assert AppLog.objects.filter(type="WARNING").count() == 1


def test_auto_luminosity_is_toggled(client, growing_plant):
    assert growing_plant.auto_luminosity
    url = reverse("growing_plant_auto_luminosity", kwargs={"plant_id": growing_plant.pk})

    response = client.post(url)
    assert response.status_code == 200
    growing_plant.refresh_from_db()
    assert not growing_plant.auto_luminosity
    assert "désactivée".encode() in response.content

    client.post(url)
    growing_plant.refresh_from_db()
    assert growing_plant.auto_luminosity
    assert AppLog.objects.filter(message__contains="lumière automatique").count() == 2


def test_a_deleted_plant_cannot_be_reached(client, growing_plant):
    growing_plant.is_deleted = True
    growing_plant.save()
    for name in ["growing_plant_detail", "growing_plant_card"]:
        assert client.get(reverse(name, kwargs={"plant_id": growing_plant.pk})).status_code == 404
    assert client.post(reverse("growing_plant_auto_luminosity",
                               kwargs={"plant_id": growing_plant.pk})).status_code == 404


# --- The signs read from the last measures ---

def test_a_plant_within_its_range_only_shows_the_sun(client, growing_plant):
    content = client.get(reverse("growing_plants")).content.decode()
    assert "plant-sign-sun" in content
    for sign in ['plant-sign-shade', 'plant-sign-hot', 'plant-sign-cold', 'plant-sign-water']:
        assert sign not in content


def test_a_plant_in_the_shade_shows_the_cloud(client, growing_plant):
    # The measure is a level: under the lit one, the plant is in the shade.
    growing_plant.current_luminosity = WELL_LIT_LEVEL - 1
    growing_plant.save()
    content = client.get(reverse("growing_plants")).content.decode()
    assert "plant-sign-shade" in content
    assert "plant-sign-sun" not in content


def test_a_plant_in_full_light_shows_the_sun(client, growing_plant):
    growing_plant.current_luminosity = WELL_LIT_LEVEL
    growing_plant.save()
    content = client.get(reverse("growing_plants")).content.decode()
    assert "plant-sign-sun" in content
    assert "plant-sign-shade" not in content


def test_the_light_sign_does_not_depend_on_the_hours_the_type_asks_for(client, growing_plant):
    # Hours a day and intensity are two different things: raising the hours the
    # species needs must not put a well lit plant in the shade.
    growing_plant.plant_type.luminosity_per_day = 99
    growing_plant.plant_type.save()
    growing_plant.current_luminosity = 4
    growing_plant.save()
    assert "plant-sign-sun" in client.get(reverse("growing_plants")).content.decode()


def test_a_plant_too_hot_shows_the_thermometer(client, growing_plant):
    growing_plant.current_temperature = growing_plant.plant_type.temperature_max + 1
    growing_plant.save()
    assert "plant-sign-hot" in client.get(reverse("growing_plants")).content.decode()


def test_a_plant_too_cold_shows_the_snowflake(client, growing_plant):
    growing_plant.current_temperature = growing_plant.plant_type.temperature_min - 1
    growing_plant.save()
    assert "plant-sign-cold" in client.get(reverse("growing_plants")).content.decode()


def test_a_plant_lacking_humidity_shows_the_water_drop(client, growing_plant):
    growing_plant.current_humidity = growing_plant.plant_type.humidity_min - 1
    growing_plant.save()
    assert "plant-sign-water" in client.get(reverse("growing_plants")).content.decode()


def test_a_light_level_off_the_scale_shows_no_light_sign(client, growing_plant):
    # A value left by an older reading is not passed off as a level.
    GrowingPlant.objects.filter(pk=growing_plant.pk).update(current_luminosity=78)
    content = client.get(reverse("growing_plants")).content.decode()
    assert "plant-sign-sun" not in content
    assert "plant-sign-shade" not in content


def test_a_plant_without_measures_shows_no_sign(client, growing_plant):
    GrowingPlant.objects.filter(pk=growing_plant.pk).update(
        current_luminosity=None, current_temperature=None, current_humidity=None)
    content = client.get(reverse("growing_plants")).content.decode()
    assert "plant-sign-" not in content


def test_the_photo_falls_back_on_the_plant_type(growing_plant):
    assert growing_plant.get_photo_url() == growing_plant.plant_type.get_photo_url()
    assert "plant-type-default.svg" in growing_plant.get_photo_url()
