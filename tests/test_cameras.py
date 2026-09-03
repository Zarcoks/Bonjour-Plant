import pytest
from django.test import Client
from django.urls import reverse

from plant_management.models import AppLog, Camera


# ── The page ──────────────────────────────────────────────────────────────────

def test_video_page(client, camera):
    response = client.get(reverse("video"))
    assert response.status_code == 200
    content = response.content.decode()
    # The camera is listed, and played: the page never opens on nothing.
    assert "Caméra du balcon" in content
    assert 'data-hls="http://192.168.1.42:8888/balcon/index.m3u8"' in content


def test_deleted_cameras_are_never_listed(client, camera):
    camera.is_deleted = True
    camera.save()
    content = client.get(reverse("video")).content.decode()
    assert "Caméra du balcon" not in content
    assert "Ajoutez une caméra" in content


def test_the_page_plays_the_camera_it_is_asked_for(client, camera):
    other = Camera.objects.create(name="Caméra du garage",
                                  stream_url="http://192.168.1.42:8888/garage/index.m3u8")
    content = client.get(reverse("video"), {'camera': other.pk}).content.decode()
    # Both are listed, only the one asked for is playing.
    assert 'data-hls="http://192.168.1.42:8888/garage/index.m3u8"' in content
    assert 'data-hls="http://192.168.1.42:8888/balcon/index.m3u8"' not in content


def test_a_camera_that_is_gone_falls_back_on_another(client, camera):
    content = client.get(reverse("video"), {'camera': camera.pk + 404}).content.decode()
    assert 'data-hls="http://192.168.1.42:8888/balcon/index.m3u8"' in content


def test_an_htmx_request_only_gets_the_stage(client, camera):
    response = client.get(reverse("video"), headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert b"balcon/index.m3u8" in response.content
    # No layout: the answer is a fragment, meant to replace the stage alone.
    assert b"<html" not in response.content


# ── Adding a camera ───────────────────────────────────────────────────────────

def test_create_returns_the_form(client, db):
    response = client.get(reverse("create_camera"))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'name="name"' in content and 'name="stream_url"' in content


def test_create(client, db, camera_payload):
    response = client.post(reverse("create_camera"), camera_payload)
    assert response.status_code == 200
    camera = Camera.objects.get(name="Caméra de la serre")
    assert camera.stream_url == "http://192.168.1.42:8888/serre/index.m3u8"
    # A camera is added to be watched: the answer comes back playing it.
    assert 'data-hls="http://192.168.1.42:8888/serre/index.m3u8"' in response.content.decode()
    assert AppLog.objects.filter(type="INFO", message__contains="a été ajoutée").count() == 1


@pytest.mark.parametrize("written, kept", [
    # The address is stored as it is written: what is served under it is the
    # business of whoever serves it.
    ("http://192.168.1.42:8888/serre/index.m3u8", "http://192.168.1.42:8888/serre/index.m3u8"),
    ("http://192.168.1.42:8888/serre", "http://192.168.1.42:8888/serre"),
    ("https://video.mon-reseau.net/serre/haut/live.m3u8", "https://video.mon-reseau.net/serre/haut/live.m3u8"),
    # What is written around the address is not part of it.
    ("  http://192.168.1.42:8888/serre  ", "http://192.168.1.42:8888/serre"),
])
def test_the_address_is_kept_as_it_is_written(client, db, camera_payload, written, kept):
    camera_payload['stream_url'] = written
    client.post(reverse("create_camera"), camera_payload)
    assert Camera.objects.get(name="Caméra de la serre").stream_url == kept


@pytest.mark.parametrize("address", [
    "192.168.1.42:8888/serre",              # no scheme at all
    "rtsp://192.168.1.42:8554/serre",       # what MediaMTX reads, not what it serves
    "http:///serre",                        # names no machine
])
def test_an_address_a_browser_cannot_follow_is_refused(client, db, camera_payload, address):
    camera_payload['stream_url'] = address
    response = client.post(reverse("create_camera"), camera_payload)
    assert response.status_code == 200
    assert not Camera.objects.filter(name="Caméra de la serre").exists()
    # The form comes back, in its own container, with what is wrong on it.
    assert response['HX-Retarget'] == '#camera-form'
    assert 'name="stream_url"' in response.content.decode()
    assert AppLog.objects.filter(type="WARNING", message__contains="a été refusée").count() == 1


# ── Changing a camera ─────────────────────────────────────────────────────────

def test_edit_returns_the_form_filled_with_the_camera(client, camera):
    response = client.get(reverse("edit_camera", kwargs={"camera_id": camera.pk}))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'value="Caméra du balcon"' in content
    assert 'value="http://192.168.1.42:8888/balcon/index.m3u8"' in content
    # It posts on the camera it was opened on, not on the creation.
    assert reverse("edit_camera", kwargs={"camera_id": camera.pk}) in content


def test_edit(client, camera):
    response = client.post(reverse("edit_camera", kwargs={"camera_id": camera.pk}),
                           {'name': "Caméra de la terrasse",
                            'stream_url': "http://192.168.1.42:8888/terrasse/index.m3u8"})
    assert response.status_code == 200
    camera.refresh_from_db()
    assert camera.name == "Caméra de la terrasse"
    assert camera.stream_url == "http://192.168.1.42:8888/terrasse/index.m3u8"
    # Changing the address is changing what is played: it comes back playing.
    assert 'data-hls="http://192.168.1.42:8888/terrasse/index.m3u8"' in response.content.decode()
    assert AppLog.objects.filter(type="INFO", message__contains="a été modifiée").count() == 1


def test_a_camera_is_reassigned_to_another_plant(client, camera, growing_plant):
    client.post(reverse("edit_camera", kwargs={"camera_id": camera.pk}),
                {'name': camera.name, 'stream_url': camera.stream_url, 'plant': growing_plant.pk})
    camera.refresh_from_db()
    assert camera.plant == growing_plant


def test_a_camera_is_freed_from_its_plant(client, camera, growing_plant):
    camera.plant = growing_plant
    camera.save()
    client.post(reverse("edit_camera", kwargs={"camera_id": camera.pk}),
                {'name': camera.name, 'stream_url': camera.stream_url})
    camera.refresh_from_db()
    assert camera.plant is None


def test_an_edition_that_cannot_be_followed_is_refused(client, camera):
    response = client.post(reverse("edit_camera", kwargs={"camera_id": camera.pk}),
                           {'name': camera.name, 'stream_url': "rtsp://192.168.1.42:8554/balcon"})
    assert response.status_code == 200
    camera.refresh_from_db()
    # Nothing is written, and the form goes home rather than into the stage.
    assert camera.stream_url == "http://192.168.1.42:8888/balcon/index.m3u8"
    assert response['HX-Retarget'] == '#camera-form'
    assert AppLog.objects.filter(type="WARNING", message__contains="a été refusée").count() == 1


def test_editing_a_camera_that_is_gone_is_not_found(client, camera):
    camera.is_deleted = True
    camera.save()
    assert client.get(reverse("edit_camera", kwargs={"camera_id": camera.pk})).status_code == 404
    assert client.post(reverse("edit_camera", kwargs={"camera_id": camera.pk}),
                       {'name': "x", 'stream_url': "http://a.b:8888/c"}).status_code == 404


# ── Removing a camera ─────────────────────────────────────────────────────────

def test_delete(client, camera):
    response = client.post(reverse("delete_camera", kwargs={"camera_id": camera.pk}))
    assert response.status_code == 204
    camera.refresh_from_db()
    # The row is kept, flagged: the page is asked to load its cameras again.
    assert camera.is_deleted
    assert response['HX-Trigger'] == 'refresh-cameras'
    assert AppLog.objects.filter(type="INFO", message__contains="a été supprimée").count() == 1


def test_deleting_a_camera_that_is_already_gone_is_not_found(client, camera):
    camera.is_deleted = True
    camera.save()
    assert client.post(reverse("delete_camera", kwargs={"camera_id": camera.pk})).status_code == 404


def test_the_delete_button_carries_the_token(client, camera):
    """
    The button posts on its own, outside of any form: nothing serialises a
    hidden field for it, so the page hands it the token as a header.
    """
    content = client.get(reverse("video")).content.decode()
    assert 'hx-headers=\'{"X-CSRFToken": "' in content


def test_a_deletion_without_the_token_is_refused(camera):
    # The test client waves CSRF through; a browser does not.
    strict = Client(enforce_csrf_checks=True)
    assert strict.post(reverse("delete_camera", kwargs={"camera_id": camera.pk})).status_code == 403
    camera.refresh_from_db()
    assert not camera.is_deleted


def test_a_deletion_carrying_the_token_goes_through(camera):
    strict = Client(enforce_csrf_checks=True)
    # Reading the page is what hands the token out, cookie and header alike.
    strict.get(reverse("video"))
    token = strict.cookies['csrftoken'].value
    response = strict.post(reverse("delete_camera", kwargs={"camera_id": camera.pk}),
                           headers={"X-CSRFToken": token})
    assert response.status_code == 204
    camera.refresh_from_db()
    assert camera.is_deleted


# ── The plant a camera watches ────────────────────────────────────────────────

def test_a_camera_is_assigned_to_a_plant(client, camera, growing_plant, camera_payload):
    camera_payload['plant'] = growing_plant.pk
    client.post(reverse("create_camera"), camera_payload)
    assert Camera.objects.get(name="Caméra de la serre").plant == growing_plant


def test_a_camera_is_assigned_to_no_plant_by_default(client, db, camera_payload):
    client.post(reverse("create_camera"), camera_payload)
    assert Camera.objects.get(name="Caméra de la serre").plant is None


def test_the_page_says_which_plant_a_camera_watches(client, camera, growing_plant):
    camera.plant = growing_plant
    camera.save()
    assert "Basilic du balcon" in client.get(reverse("video")).content.decode()


def test_the_plant_reads_the_camera_watching_it(camera, growing_plant):
    assert growing_plant.camera() is None
    camera.plant = growing_plant
    camera.save()
    assert growing_plant.camera() == camera


def test_a_deleted_camera_no_longer_watches_its_plant(camera, growing_plant):
    camera.plant = growing_plant
    camera.is_deleted = True
    camera.save()
    assert growing_plant.camera() is None


def test_the_cameras_of_a_deleted_plant_are_freed(client, camera, growing_plant):
    camera.plant = growing_plant
    camera.save()
    client.post(reverse("delete_growing_plant", kwargs={"plant_id": growing_plant.pk}))
    camera.refresh_from_db()
    assert camera.plant is None
