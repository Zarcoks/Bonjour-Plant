from django.core.management.base import BaseCommand

from core.app import app
from plant_management.models import PlantType

logger = app.module_logger("data_setup")

# The plant types the application knows out of the box.
DEFAULT_PLANT_TYPES = [
    {'plant_name': 'Basilic', 'humidity_min': 60, 'humidity_max': 80, 'temperature_min': 18.0,
     'temperature_max': 27.0, 'luminosity_per_day': 6, 'harvest_days': 60},
    {'plant_name': 'Tomate cerise', 'humidity_min': 50, 'humidity_max': 70, 'temperature_min': 18.0,
     'temperature_max': 30.0, 'luminosity_per_day': 8, 'harvest_days': 90},
    {'plant_name': 'Menthe', 'humidity_min': 65, 'humidity_max': 85, 'temperature_min': 15.0,
     'temperature_max': 25.0, 'luminosity_per_day': 5, 'harvest_days': 45},
    {'plant_name': 'Laitue', 'humidity_min': 60, 'humidity_max': 75, 'temperature_min': 10.0,
     'temperature_max': 22.0, 'luminosity_per_day': 5, 'harvest_days': 50},
    {'plant_name': 'Fraisier', 'humidity_min': 55, 'humidity_max': 75, 'temperature_min': 15.0,
     'temperature_max': 26.0, 'luminosity_per_day': 7, 'harvest_days': 120},
    {'plant_name': 'Persil', 'humidity_min': 60, 'humidity_max': 80, 'temperature_min': 12.0,
     'temperature_max': 24.0, 'luminosity_per_day': 4, 'harvest_days': 70},
]


class Command(BaseCommand):
    help = "Sets up the plant types the application knows by default."

    def handle(self, *args, **options):
        for plant_type in DEFAULT_PLANT_TYPES:
            _, created = PlantType.objects.get_or_create(plant_name=plant_type['plant_name'], defaults=plant_type)
            if created:
                logger.info("Le type de plante " + plant_type['plant_name'] + " a été installé")
        self.stdout.write(self.style.SUCCESS("Plant types are set up."))
