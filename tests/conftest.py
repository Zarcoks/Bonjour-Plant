import io

import pytest
from PIL import Image

from plant_management.models import PlantType


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
