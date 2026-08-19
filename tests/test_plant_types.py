from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from plant_management.models import AppLog, PlantType


def test_plant_types_page(client, plant_type):
    response = client.get(reverse("plant_types"))
    assert response.status_code == 200
    # The card shows the name and the harvest days.
    assert b"Basilic" in response.content
    assert b"60" in response.content


def test_plant_type_detail_returns_the_edition_form(client, plant_type):
    response = client.get(reverse("plant_type_detail", kwargs={"plant_type_id": plant_type.pk}))
    assert response.status_code == 200
    # The fields missing from the collapsed card are now there, along with both buttons.
    assert b'name="luminosity_per_day"' in response.content
    assert b'name="photo"' in response.content
    assert "Valider".encode() in response.content
    assert "Annuler".encode() in response.content


def test_plant_type_card_returns_the_collapsed_card(client, plant_type):
    response = client.get(reverse("plant_type_card", kwargs={"plant_type_id": plant_type.pk}))
    assert response.status_code == 200
    assert b'name="luminosity_per_day"' not in response.content


def test_plant_type_update(client, plant_type, plant_type_payload):
    plant_type_payload['plant_name'] = "Basilic thaï"
    response = client.post(reverse("plant_type_detail", kwargs={"plant_type_id": plant_type.pk}), plant_type_payload)
    assert response.status_code == 200
    plant_type.refresh_from_db()
    assert plant_type.plant_name == "Basilic thaï"
    assert plant_type.harvest_days == 45
    # The answer is the collapsed card, and the change is logged.
    assert b'name="luminosity_per_day"' not in response.content
    assert AppLog.objects.filter(type="INFO", message__contains="Basilic thaï").count() == 1


def test_plant_type_update_with_invalid_range_sends_the_form_back(client, plant_type, plant_type_payload):
    plant_type_payload['humidity_min'] = 90
    plant_type_payload['humidity_max'] = 10
    response = client.post(reverse("plant_type_detail", kwargs={"plant_type_id": plant_type.pk}), plant_type_payload)
    assert response.status_code == 200
    plant_type.refresh_from_db()
    assert plant_type.humidity_min == 60
    assert b'name="humidity_max"' in response.content
    assert AppLog.objects.filter(type="WARNING").count() == 1


def test_plant_type_create_form(client, db):
    response = client.get(reverse("create_plant_type"))
    assert response.status_code == 200
    assert b'name="plant_name"' in response.content


def test_plant_type_create(client, db, plant_type_payload):
    response = client.post(reverse("create_plant_type"), plant_type_payload)
    assert response.status_code == 200
    created = PlantType.objects.get(plant_name="Menthe")
    # No photo given: the default illustration is used.
    assert not created.photo
    assert "plant-type-default.svg" in created.get_photo_url()
    # The answer appends the new card and clears the creation form out of band.
    assert b"Menthe" in response.content
    assert b'hx-swap-oob' in response.content
    assert AppLog.objects.filter(type="INFO", message__contains="Menthe").count() == 1


def test_plant_type_create_with_invalid_input_is_retargeted_to_the_form(client, db, plant_type_payload):
    del plant_type_payload['plant_name']
    response = client.post(reverse("create_plant_type"), plant_type_payload)
    assert response.status_code == 200
    assert not PlantType.objects.exists()
    assert response['HX-Retarget'] == '#plant-type-create'
    assert response['HX-Reswap'] == 'innerHTML'


def test_plant_type_update_with_a_photo(client, plant_type, plant_type_payload, settings, tmp_path, png_bytes):
    settings.MEDIA_ROOT = tmp_path
    photo = SimpleUploadedFile("basilic.png", png_bytes, content_type="image/png")
    response = client.post(reverse("plant_type_detail", kwargs={"plant_type_id": plant_type.pk}),
                           dict(plant_type_payload, photo=photo))
    assert response.status_code == 200
    plant_type.refresh_from_db()
    assert plant_type.photo.name.startswith("plant_types/basilic")
    # The card now shows the uploaded photo instead of the default illustration.
    assert plant_type.photo.url in response.content.decode()
    assert "plant-type-default.svg" not in response.content.decode()


def test_plant_type_create_with_a_photo(client, db, plant_type_payload, settings, tmp_path, png_bytes):
    settings.MEDIA_ROOT = tmp_path
    photo = SimpleUploadedFile("menthe.png", png_bytes, content_type="image/png")
    response = client.post(reverse("create_plant_type"), dict(plant_type_payload, photo=photo))
    assert response.status_code == 200
    created = PlantType.objects.get(plant_name="Menthe")
    assert created.photo
    assert created.photo.url in response.content.decode()
