from django.urls import reverse

from core.app import app
from plant_management.models import AppLog
from plant_management.pages.logs.views import LOGS_SHOWN


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


def test_at_most_two_hundred_logs_are_shown(client, db):
    AppLog.objects.bulk_create([AppLog(message="log numéro {}".format(number), type="DEBUG")
                                for number in range(250)])
    content = client.get(reverse("logs")).content.decode()
    # One row per log, plus the header row.
    assert content.count("<tr>") == LOGS_SHOWN + 1


def test_the_two_hundred_shown_are_the_newest_ones(client, db):
    AppLog.objects.bulk_create([AppLog(message="log numéro {}".format(number), type="DEBUG")
                                for number in range(250)])
    content = client.get(reverse("logs")).content.decode()
    # Written in the same second: the newest of the batch opens the table,
    # the oldest ones are left out.
    assert content.index("log numéro 249") < content.index("log numéro 248")
    assert content.index("log numéro 51") < content.index("log numéro 50")
    assert "log numéro 49" not in content
    assert "log numéro 0<" not in content


def test_the_limit_applies_to_a_filtered_table_too(client, db):
    AppLog.objects.bulk_create([AppLog(message="bruit {}".format(number), type="DEBUG")
                                for number in range(250)])
    app.logger.info("une information isolée")
    content = client.get(reverse("logs"), {'search': "bruit"}).content.decode()
    assert content.count("<tr>") == LOGS_SHOWN + 1
    assert "une information isolée" not in content
