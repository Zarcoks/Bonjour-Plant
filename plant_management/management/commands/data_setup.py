import datetime

from django.core.management.base import BaseCommand

from core.app import app
from plant_management.models import GrowingPlant, PlantType

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


# A few plants to start with, so that the main page is not empty. The measures
# are picked to show each sign of the cards: enough light or shade, too hot or
# too cold, lack of humidity.
DEFAULT_GROWING_PLANTS = [
    {'display_name': "Basilic du balcon", 'plant_type': "Basilic", 'planted_days_ago': 42,
     'watered_hours_ago': 8, 'growing_state': 70, 'current_temperature': 24.0,
     'current_humidity': 72, 'current_luminosity': 7, 'auto_luminosity': True},
    {'display_name': "Tomates de la serre", 'plant_type': "Tomate cerise", 'planted_days_ago': 21,
     'watered_hours_ago': 30, 'growing_state': 23, 'current_temperature': 33.5,
     'current_humidity': 44, 'current_luminosity': 9, 'auto_luminosity': True},
    {'display_name': "Fraisier du jardin", 'plant_type': "Fraisier", 'planted_days_ago': 65,
     'watered_hours_ago': 52, 'growing_state': 54, 'current_temperature': 11.5,
     'current_humidity': 61, 'current_luminosity': 3, 'auto_luminosity': False},
    {'display_name': "Menthe de la cuisine", 'plant_type': "Menthe", 'planted_days_ago': 12,
     'watered_hours_ago': 3, 'growing_state': 27, 'current_temperature': 21.0,
     'current_humidity': 70, 'current_luminosity': 5, 'auto_luminosity': True},
    {'display_name': "Laitue d'hiver", 'plant_type': "Laitue", 'planted_days_ago': 96,
     'watered_hours_ago': 240, 'growing_state': 100, 'current_temperature': 17.0,
     'current_humidity': 66, 'current_luminosity': 5, 'auto_luminosity': False,
     'harvested': True},
]


class Command(BaseCommand):
    help = "Sets up the plant types the application knows by default."

    def handle(self, *args, **options):
        for plant_type in DEFAULT_PLANT_TYPES:
            _, created = PlantType.objects.get_or_create(plant_name=plant_type['plant_name'], defaults=plant_type)
            if created:
                logger.info("Le type de plante " + plant_type['plant_name'] + " a été installé")

        for plant in DEFAULT_GROWING_PLANTS:
            fields = dict(plant)
            planted_days_ago = fields.pop('planted_days_ago')
            watered_hours_ago = fields.pop('watered_hours_ago')
            fields['plant_type'] = PlantType.objects.get(plant_name=fields['plant_type'])
            fields['planted_date'] = datetime.datetime.now() - datetime.timedelta(days=planted_days_ago)
            fields['last_watering'] = datetime.datetime.now() - datetime.timedelta(hours=watered_hours_ago)
            _, created = GrowingPlant.objects.get_or_create(display_name=fields['display_name'], defaults=fields)
            if created:
                logger.info("La plante " + fields['display_name'] + " a été plantée")

        self.stdout.write(self.style.SUCCESS("Plant types and growing plants are set up."))
