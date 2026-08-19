from django.urls import reverse

from core.app import app
from plant_management.models import AppLog


def test_logs_page(client, db):
    app.logger.info("le type de plante Menthe a été créé")
    app.logger.error("la sonde du salon ne répond pas")
    response = client.get(reverse("logs"))
    assert response.status_code == 200
    assert "le type de plante Menthe a été créé".encode() in response.content
    assert b"ERROR" in response.content


def test_logs_are_shown_newest_first(client, db):
    app.logger.info("la première")
    app.logger.info("la seconde")
    content = client.get(reverse("logs")).content.decode()
    assert content.index("la seconde") < content.index("la première")


def test_logs_filtered_by_level(client, db):
    app.logger.info("une information")
    app.logger.error("une erreur")
    response = client.get(reverse("logs"), {'type': "ERROR"})
    assert "une erreur".encode() in response.content
    assert "une information".encode() not in response.content


def test_logs_filtered_by_search(client, db):
    app.logger.info("le type de plante Menthe a été créé")
    app.logger.info("le type de plante Basilic a été modifié")
    response = client.get(reverse("logs"), {'search': "menthe"})
    assert b"Menthe" in response.content
    assert b"Basilic" not in response.content


def test_logs_filtered_by_date(client, db):
    app.logger.info("une log du jour")
    log_date = AppLog.objects.get().time.date()
    assert b"une log du jour" in client.get(reverse("logs"), {'date': log_date.isoformat()}).content
    assert b"une log du jour" not in client.get(reverse("logs"), {'date': "2020-01-01"}).content


def test_an_htmx_request_only_gets_the_table(client, db):
    app.logger.info("une information")
    response = client.get(reverse("logs"), headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert b"<table" in response.content
    # No layout: the answer is a fragment, meant to replace the table alone.
    assert b"<html" not in response.content


def test_an_unknown_level_filter_is_ignored(client, db):
    app.logger.info("une information")
    response = client.get(reverse("logs"), {'type': "PANIC"})
    assert response.status_code == 200
    assert "une information".encode() in response.content
