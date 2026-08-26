"""The metrics page: the state of a plant, then its measures over time."""
import datetime
import json

import pytest
from django.urls import reverse

from plant_management.models import Sensor, SensorData
from plant_management.pages.metrics.views import METRICS_DAYS


@pytest.fixture
def watched(sensor, growing_plant):
    sensor.plant = growing_plant
    sensor.save()
    return sensor


def measure(sensor, payload, hours_ago=0):
    data = SensorData.objects.create(sensor=sensor, plant=sensor.plant, payload=payload)
    if hours_ago:
        SensorData.objects.filter(pk=data.pk).update(time=data.time - datetime.timedelta(hours=hours_ago))
    return data


def points_of(response, field):
    """The series the page handed to the chart of that measure."""
    content = response.content.decode()
    opening = '<script id="{}" type="application/json">'.format(field)
    start = content.index(opening) + len(opening)
    return json.loads(content[start:content.index('</script>', start)])


# --- The page ---

def test_the_page_opens_on_the_first_plant(client, growing_plant):
    response = client.get(reverse("metrics"))
    assert response.status_code == 200
    assert "Basilic du balcon" in response.content.decode()


def test_a_plant_can_be_asked_for(client, growing_plant, harvested_plant):
    content = client.get(reverse("metrics"), {'plant': harvested_plant.pk}).content.decode()
    assert "Laitue d&#x27;hiver" in content


def test_harvested_plants_are_offered_too(client, growing_plant, harvested_plant):
    content = client.get(reverse("metrics")).content.decode()
    # Named as harvested in the picker, so the choice is not misleading.
    assert "Laitue d&#x27;hiver (récoltée)" in content


def test_a_deleted_plant_is_not_offered(client, growing_plant):
    growing_plant.is_deleted = True
    growing_plant.save()
    content = client.get(reverse("metrics")).content.decode()
    assert "Basilic du balcon" not in content
    assert "Aucune plante à suivre" in content


def test_the_state_of_the_plant_is_shown(client, watched, growing_plant):
    content = client.get(reverse("metrics")).content.decode()
    assert "Basilic du balcon" in content        # name
    assert "Basilic" in content                  # type
    assert "Planté le 8 juillet 2026" in content  # planting date
    assert "72" in content                       # current humidity
    assert "24" in content                       # current temperature
    assert "plant-type-default.svg" in content   # photo


def test_a_harvested_plant_says_so(client, harvested_plant):
    content = client.get(reverse("metrics"), {'plant': harvested_plant.pk}).content.decode()
    assert "Récoltée" in content
    assert "le 2 août 2026" in content


def test_an_htmx_request_only_gets_the_panel(client, growing_plant):
    response = client.get(reverse("metrics"), headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert b"plant-summary" in response.content
    # No layout: the answer replaces the panel alone.
    assert b"<html" not in response.content


# --- The curves ---

def test_the_three_curves_are_built(client, watched):
    measure(watched, '{"humidity": 65, "luminosity": "high", "temperature": 21.5}')
    response = client.get(reverse("metrics"))
    assert points_of(response, 'current_humidity') == [
        {'x': points_of(response, 'current_humidity')[0]['x'], 'y': 65}]
    assert points_of(response, 'current_luminosity')[0]['y'] == 3
    assert points_of(response, 'current_temperature')[0]['y'] == 21.5


def test_the_points_are_in_time_order(client, watched):
    measure(watched, '{"humidity": 60}', hours_ago=3)
    measure(watched, '{"humidity": 70}', hours_ago=1)
    points = points_of(client.get(reverse("metrics")), 'current_humidity')
    assert [point['y'] for point in points] == [60, 70]
    assert points[0]['x'] < points[1]['x']


def test_the_keys_of_the_sensor_are_the_ones_read(client, watched):
    watched.humidity_payload_label = "hum"
    watched.save()
    measure(watched, '{"hum": 44}')
    assert points_of(client.get(reverse("metrics")), 'current_humidity')[0]['y'] == 44


def test_two_sensors_feed_the_same_curves(client, watched, growing_plant):
    other = Sensor.objects.create(name="Thermomètre", model="Test", mqtt_topic="serre",
                                 plant=growing_plant, temperature_payload_label="temp")
    measure(watched, '{"humidity": 65}')
    measure(other, '{"temp": 26.5}')
    response = client.get(reverse("metrics"))
    assert len(points_of(response, 'current_humidity')) == 1
    assert points_of(response, 'current_temperature')[0]['y'] == 26.5


def test_measures_older_than_the_window_are_left_out(client, watched):
    measure(watched, '{"humidity": 10}', hours_ago=24 * (METRICS_DAYS + 1))
    measure(watched, '{"humidity": 65}')
    points = points_of(client.get(reverse("metrics")), 'current_humidity')
    assert [point['y'] for point in points] == [65]


def test_an_unreadable_payload_is_skipped(client, watched):
    measure(watched, "pas du json")
    measure(watched, '{"humidity": 65}')
    assert len(points_of(client.get(reverse("metrics")), 'current_humidity')) == 1


def test_a_plant_without_measures_says_so(client, watched):
    content = client.get(reverse("metrics")).content.decode()
    assert "Aucune mesure sur la période." in content
    assert 'data-metric' not in content


def test_the_measures_of_another_plant_are_not_mixed_in(client, watched, harvested_plant):
    measure(watched, '{"humidity": 65}')
    content = client.get(reverse("metrics"), {'plant': harvested_plant.pk}).content.decode()
    assert "Aucune mesure sur la période." in content


def test_the_light_curve_carries_the_names_of_its_levels(client, watched):
    measure(watched, '{"luminosity": "nor"}')
    content = client.get(reverse("metrics")).content.decode()
    # The axis reads in words, and so does the table.
    assert 'data-ticks="très faible|faible|normale|forte|très forte"' in content
    assert "normale" in content


# --- The values, without hovering ---

def test_a_table_lets_the_values_be_read(client, watched):
    measure(watched, '{"humidity": 65, "temperature": 21.5}')
    content = client.get(reverse("metrics")).content.decode()
    assert "Voir les valeurs" in content
    assert "metric-table" in content


def test_the_table_shows_the_newest_first(client, watched):
    measure(watched, '{"humidity": 60}', hours_ago=3)
    measure(watched, '{"humidity": 70}')
    content = client.get(reverse("metrics")).content.decode()
    table = content[content.index('metric-table'):]
    assert table.index("70") < table.index("60")
