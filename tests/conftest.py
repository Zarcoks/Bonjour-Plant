import datetime
import io

import pytest
from PIL import Image

from plant_management.models import Actionner, GrowingPlant, PlantType, Sensor


@pytest.fixture(autouse=True)
def local_cache(settings):
    """Tests run on a cache of their own: no Redis to reach, nothing shared."""
    settings.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
    from django.core.cache import cache
    cache.clear()
    yield cache
    cache.clear()


@pytest.fixture
def png_bytes():
    """A real (tiny) PNG, so that the ImageField validation passes."""
    buffer = io.BytesIO()
    Image.new("RGB", (12, 12), (47, 158, 98)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def plant_type(db):
    return PlantType.objects.create(
        plant_name="Basilic",
        humidity_min=60,
        humidity_max=80,
        temperature_min=18.0,
        temperature_max=27.0,
        luminosity_per_day=6,
        harvest_days=60,
    )


@pytest.fixture
def plant_type_payload():
    return {
        'plant_name': "Menthe",
        'humidity_min': 65,
        'humidity_max': 85,
        'temperature_min': 15.0,
        'temperature_max': 25.0,
        'luminosity_per_day': 5,
        'harvest_days': 45,
    }


@pytest.fixture
def growing_plant(plant_type):
    """A plant growing well: warm enough, damp enough, and in the light."""
    return GrowingPlant.objects.create(
        display_name="Basilic du balcon",
        plant_type=plant_type,
        planted_date=datetime.datetime(2026, 7, 8, 9, 30),
        last_watering=datetime.datetime(2026, 8, 18, 20, 0),
        growing_state=70,
        current_temperature=24.0,
        current_humidity=72,
        current_luminosity=3,  # niveau « high »
        auto_luminosity=True,
    )


@pytest.fixture
def harvested_plant(plant_type):
    return GrowingPlant.objects.create(
        display_name="Laitue d'hiver",
        plant_type=plant_type,
        planted_date=datetime.datetime(2026, 5, 15, 9, 30),
        growing_state=100,
        harvested=True,
        harvest_day=datetime.datetime(2026, 8, 2, 11, 0),
    )


@pytest.fixture
def growing_plant_payload(plant_type):
    return {
        'display_name': "Basilic de la fenêtre",
        'plant_type': plant_type.pk,
        'planted_date': "2026-03-12",
    }


@pytest.fixture
def sensor(db):
    return Sensor.objects.create(
        name="Sonde d'humidité du balcon",
        model="Zigbee SM-100",
        mqtt_topic="bonjour-plant/balcon/humidity",
    )


@pytest.fixture
def sensor_payload():
    return {
        'name': "Thermomètre de la serre",
        'model': "Zigbee TH-220",
        'mqtt_topic': "bonjour-plant/serre/temperature",
        'plant': "",
    }


@pytest.fixture
def actionner(db):
    return Actionner.objects.create(
        name="Lampe UV du balcon",
        act_on="luminosity",
        mqtt_topic="bonjour-plant/balcon/lampe/set",
    )


@pytest.fixture
def actionner_payload():
    return {
        'name': "Humidificateur de la serre",
        'act_on': "humidity",
        'mqtt_topic': "bonjour-plant/serre/brumisateur/set",
        'plant': "",
    }
