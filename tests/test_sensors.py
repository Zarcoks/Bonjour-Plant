from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from plant_management.models import AppLog, Sensor


def test_sensors_page(client, sensor):
    response = client.get(reverse("sensors"))
    assert response.status_code == 200
    content = response.content.decode()
    # The card shows the name, the model and the assignment.
    assert "Sonde d&#x27;humidité du balcon" in content
    assert "Zigbee SM-100" in content
    assert "Assigné à aucune plante" in content


def test_deleted_sensors_are_never_listed(client, sensor):
    sensor.is_deleted = True
    sensor.save()
    assert b"Zigbee SM-100" not in client.get(reverse("sensors")).content


def test_an_htmx_request_only_gets_the_grid(client, sensor):
    response = client.get(reverse("sensors"), headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert b"Zigbee SM-100" in response.content
    # No layout: the answer is a fragment, meant to replace the grid alone.
    assert b"<html" not in response.content


def test_detail_returns_the_edition_form(client, sensor):
    response = client.get(reverse("sensor_detail", kwargs={"sensor_id": sensor.pk}))
    assert response.status_code == 200
    content = response.content.decode()
    for field in ['name="name"', 'name="model"', 'name="mqtt_topic"', 'name="plant"', 'name="photo"']:
        assert field in content
    assert "Valider" in content and "Annuler" in content and "Supprimer" in content


def test_card_returns_the_collapsed_card(client, sensor):
    response = client.get(reverse("sensor_card", kwargs={"sensor_id": sensor.pk}))
    assert response.status_code == 200
    assert b'name="mqtt_topic"' not in response.content


def test_update(client, sensor, sensor_payload):
    response = client.post(reverse("sensor_detail", kwargs={"sensor_id": sensor.pk}), sensor_payload)
    assert response.status_code == 200
    sensor.refresh_from_db()
    assert sensor.name == "Thermomètre de la serre"
    assert sensor.mqtt_topic == "bonjour-plant/serre/temperature"
    # The answer is the collapsed card, and the change is logged.
    assert b'name="mqtt_topic"' not in response.content
    assert AppLog.objects.filter(type="INFO", message__contains="a été modifié").count() == 1


def test_update_without_a_topic_sends_the_form_back(client, sensor, sensor_payload):
    sensor_payload['mqtt_topic'] = ""
    response = client.post(reverse("sensor_detail", kwargs={"sensor_id": sensor.pk}), sensor_payload)
    assert response.status_code == 200
    sensor.refresh_from_db()
    assert sensor.name == "Sonde d'humidité du balcon"
    assert b'name="mqtt_topic"' in response.content
    assert AppLog.objects.filter(type="WARNING").count() == 1


# --- Assignment ---

def test_the_form_offers_the_plants_and_no_plant_at_all(client, sensor, growing_plant):
    content = client.get(reverse("sensor_detail", kwargs={"sensor_id": sensor.pk})).content.decode()
    assert "aucune plante" in content
    assert "Basilic du balcon" in content
    assert "Assigner à" in content


def test_a_sensor_is_assigned_to_a_plant(client, sensor, growing_plant, sensor_payload):
    sensor_payload['plant'] = growing_plant.pk
    response = client.post(reverse("sensor_detail", kwargs={"sensor_id": sensor.pk}), sensor_payload)
    assert response.status_code == 200
    sensor.refresh_from_db()
    assert sensor.plant == growing_plant
    assert "Assigné à" in response.content.decode()
    assert "Basilic du balcon" in response.content.decode()


def test_a_sensor_is_assigned_back_to_nothing(client, sensor, growing_plant, sensor_payload):
    sensor.plant = growing_plant
    sensor.save()
    response = client.post(reverse("sensor_detail", kwargs={"sensor_id": sensor.pk}), sensor_payload)
    sensor.refresh_from_db()
    assert sensor.plant is None
    assert "Assigné à aucune plante" in response.content.decode()


def test_a_deleted_plant_is_not_offered(client, sensor, growing_plant):
    growing_plant.is_deleted = True
    growing_plant.save()
    content = client.get(reverse("sensor_detail", kwargs={"sensor_id": sensor.pk})).content.decode()
    assert "Basilic du balcon" not in content


def test_deleting_a_plant_frees_its_sensors(client, sensor, growing_plant):
    sensor.plant = growing_plant
    sensor.save()
    client.post(reverse("delete_growing_plant", kwargs={"plant_id": growing_plant.pk}))
    sensor.refresh_from_db()
    assert sensor.plant is None
    assert not sensor.is_deleted


# --- Creation ---

def test_create_form(client, db):
    response = client.get(reverse("create_sensor"))
    assert response.status_code == 200
    assert b'name="mqtt_topic"' in response.content


def test_create(client, db, sensor_payload):
    response = client.post(reverse("create_sensor"), sensor_payload)
    assert response.status_code == 200
    created = Sensor.objects.get(name="Thermomètre de la serre")
    # No photo given: the default illustration is used.
    assert not created.photo
    assert "sensor-default.svg" in created.get_photo_url()
    assert created.plant is None
    # The answer appends the new card and clears the creation form out of band.
    assert "Thermomètre de la serre" in response.content.decode()
    assert b'hx-swap-oob' in response.content
    assert AppLog.objects.filter(type="INFO", message__contains="a été créé").count() == 1


def test_create_assigned_to_a_plant(client, growing_plant, sensor_payload):
    sensor_payload['plant'] = growing_plant.pk
    client.post(reverse("create_sensor"), sensor_payload)
    assert Sensor.objects.get(name="Thermomètre de la serre").plant == growing_plant


def test_create_with_invalid_input_is_retargeted_to_the_form(client, db, sensor_payload):
    del sensor_payload['name']
    response = client.post(reverse("create_sensor"), sensor_payload)
    assert response.status_code == 200
    assert not Sensor.objects.exists()
    assert response['HX-Retarget'] == '#sensor-create'
    assert response['HX-Reswap'] == 'innerHTML'


def test_create_with_a_photo(client, db, sensor_payload, settings, tmp_path, png_bytes):
    settings.MEDIA_ROOT = tmp_path
    photo = SimpleUploadedFile("sonde.png", png_bytes, content_type="image/png")
    response = client.post(reverse("create_sensor"), dict(sensor_payload, photo=photo))
    assert response.status_code == 200
    created = Sensor.objects.get(name="Thermomètre de la serre")
    assert created.photo.name.startswith("sensors/sonde")
    assert created.photo.url in response.content.decode()


# --- Deletion ---

def test_delete_flags_the_sensor_and_asks_the_page_to_reload_its_grid(client, sensor):
    response = client.post(reverse("delete_sensor", kwargs={"sensor_id": sensor.pk}))
    assert response.status_code == 204
    assert response['HX-Trigger'] == 'refresh-sensors'
    sensor.refresh_from_db()
    # The row stays, flagged as deleted, and leaves the grid.
    assert sensor.is_deleted
    assert b"Zigbee SM-100" not in client.get(reverse("sensors")).content
    assert AppLog.objects.filter(type="INFO", message__contains="a été supprimé").count() == 1


def test_a_sensor_cannot_be_deleted_twice(client, sensor):
    url = reverse("delete_sensor", kwargs={"sensor_id": sensor.pk})
    assert client.post(url).status_code == 204
    assert client.post(url).status_code == 404


def test_a_deleted_sensor_cannot_be_reached(client, sensor):
    sensor.is_deleted = True
    sensor.save()
    for name in ["sensor_detail", "sensor_card"]:
        assert client.get(reverse(name, kwargs={"sensor_id": sensor.pk})).status_code == 404


# --- Reading the payload of a sensor ---

def test_a_new_sensor_names_its_measures_the_usual_way(client, db, sensor_payload):
    client.post(reverse("create_sensor"), sensor_payload)
    created = Sensor.objects.get(name="Thermomètre de la serre")
    assert created.humidity_payload_label == "humidity"
    assert created.luminosity_payload_label == "luminosity"
    assert created.temperature_payload_label == "temperature"


def test_the_labels_can_be_chosen_at_creation(client, db, sensor_payload):
    client.post(reverse("create_sensor"), dict(sensor_payload, temperature_payload_label="temp"))
    assert Sensor.objects.get(name="Thermomètre de la serre").temperature_payload_label == "temp"


def test_the_labels_are_shown_in_both_forms(client, sensor):
    for url in [reverse("create_sensor"), reverse("sensor_detail", kwargs={"sensor_id": sensor.pk})]:
        content = client.get(url).content.decode()
        for field in ['name="humidity_payload_label"', 'name="luminosity_payload_label"',
                      'name="temperature_payload_label"']:
            assert field in content
        assert "clé du payload" in content


def test_the_labels_can_be_edited(client, sensor, sensor_payload):
    response = client.post(reverse("sensor_detail", kwargs={"sensor_id": sensor.pk}),
                           dict(sensor_payload, humidity_payload_label="hum",
                                luminosity_payload_label="lux", temperature_payload_label="temp"))
    assert response.status_code == 200
    sensor.refresh_from_db()
    assert (sensor.humidity_payload_label, sensor.luminosity_payload_label,
            sensor.temperature_payload_label) == ("hum", "lux", "temp")


def test_a_label_left_empty_goes_back_to_the_usual_name(client, sensor, sensor_payload):
    sensor.humidity_payload_label = "hum"
    sensor.save()
    client.post(reverse("sensor_detail", kwargs={"sensor_id": sensor.pk}),
                dict(sensor_payload, humidity_payload_label=""))
    sensor.refresh_from_db()
    assert sensor.humidity_payload_label == "humidity"


def test_a_label_emptied_outside_the_interface_still_reads(db):
    sensor = Sensor.objects.create(name="Sonde muette", model="Test", mqtt_topic="test",
                                   humidity_payload_label="", luminosity_payload_label="",
                                   temperature_payload_label="")
    assert sensor.get_humidity_label() == "humidity"
    assert sensor.get_luminosity_label() == "luminosity"
    assert sensor.get_temperature_label() == "temperature"


def test_a_chosen_label_is_the_one_read(db):
    sensor = Sensor.objects.create(name="Luxmètre", model="Test", mqtt_topic="test",
                                   luminosity_payload_label="lux")
    assert sensor.get_luminosity_label() == "lux"
