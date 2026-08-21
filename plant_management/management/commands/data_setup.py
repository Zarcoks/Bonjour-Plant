import datetime

from django.core.management.base import BaseCommand

from core.app import app
from plant_management.models import Actionner, GrowingPlant, PlantType, Sensor

logger = app.module_logger("data_setup")

# The plant types the application knows out of the box.
DEFAULT_PLANT_TYPES = [
    {'plant_name': 'Basilic', 'humidity_min': 60, 'humidity_max': 80, 'temperature_min': 18.0,
     'temperature_max': 27.0, 'light_starts_at': datetime.time(8, 0),
     'light_ends_at': datetime.time(20, 0), 'harvest_days': 60},
    {'plant_name': 'Tomate cerise', 'humidity_min': 50, 'humidity_max': 70, 'temperature_min': 18.0,
     'temperature_max': 30.0, 'light_starts_at': datetime.time(7, 0),
     'light_ends_at': datetime.time(21, 0), 'harvest_days': 90},
    {'plant_name': 'Menthe', 'humidity_min': 65, 'humidity_max': 85, 'temperature_min': 15.0,
     'temperature_max': 25.0, 'light_starts_at': datetime.time(9, 0),
     'light_ends_at': datetime.time(19, 0), 'harvest_days': 45},
    {'plant_name': 'Laitue', 'humidity_min': 60, 'humidity_max': 75, 'temperature_min': 10.0,
     'temperature_max': 22.0, 'light_starts_at': datetime.time(8, 30),
     'light_ends_at': datetime.time(18, 30), 'harvest_days': 50},
    {'plant_name': 'Fraisier', 'humidity_min': 55, 'humidity_max': 75, 'temperature_min': 15.0,
     'temperature_max': 26.0, 'light_starts_at': datetime.time(7, 30),
     'light_ends_at': datetime.time(20, 30), 'harvest_days': 120},
    {'plant_name': 'Persil', 'humidity_min': 60, 'humidity_max': 80, 'temperature_min': 12.0,
     'temperature_max': 24.0, 'light_starts_at': datetime.time(9, 30),
     'light_ends_at': datetime.time(19, 0), 'harvest_days': 70},
]


# A few plants to start with, so that the main page is not empty. The measures
# are picked to show each sign of the cards: enough light or shade, too hot or
# too cold, lack of humidity.
DEFAULT_GROWING_PLANTS = [
    {'display_name': "Basilic du balcon", 'plant_type': "Basilic", 'planted_days_ago': 42,
     'watered_hours_ago': 8, 'growing_state': 70, 'current_temperature': 24.0,
     'current_humidity': 72, 'current_luminosity': 3, 'auto_luminosity': True},
    {'display_name': "Tomates de la serre", 'plant_type': "Tomate cerise", 'planted_days_ago': 21,
     'watered_hours_ago': 30, 'growing_state': 23, 'current_temperature': 33.5,
     'current_humidity': 44, 'current_luminosity': 4, 'auto_luminosity': True},
    {'display_name': "Fraisier du jardin", 'plant_type': "Fraisier", 'planted_days_ago': 65,
     'watered_hours_ago': 52, 'growing_state': 54, 'current_temperature': 11.5,
     'current_humidity': 61, 'current_luminosity': 1, 'auto_luminosity': False},
    {'display_name': "Menthe de la cuisine", 'plant_type': "Menthe", 'planted_days_ago': 12,
     'watered_hours_ago': 3, 'growing_state': 27, 'current_temperature': 21.0,
     'current_humidity': 70, 'current_luminosity': 2, 'auto_luminosity': True},
    {'display_name': "Laitue d'hiver", 'plant_type': "Laitue", 'planted_days_ago': 96,
     'watered_hours_ago': 240, 'growing_state': 100, 'current_temperature': 17.0,
     'current_humidity': 66, 'current_luminosity': 2, 'auto_luminosity': False,
     'harvested': True},
]


# A few sensors, one of them assigned to no plant at all.
DEFAULT_SENSORS = [
    {'name': "Sonde d'humidité du balcon", 'model': "Zigbee SM-100",
     'mqtt_topic': "bonjour-plant/balcon/humidity", 'plant': "Basilic du balcon"},
    {'name': "Thermomètre de la serre", 'model': "Zigbee TH-220",
     'mqtt_topic': "bonjour-plant/serre/temperature", 'plant': "Tomates de la serre",
     'temperature_payload_label': "temp"},
    {'name': "Luxmètre du jardin", 'model': "LoRa LX-40",
     'mqtt_topic': "bonjour-plant/jardin/luminosity", 'plant': "Fraisier du jardin",
     'luminosity_payload_label': "lux"},
    {'name': "Sonde d'humidité de rechange", 'model': "Zigbee SM-100",
     'mqtt_topic': "bonjour-plant/atelier/humidity", 'plant': None},
]


# A few actionners, one of them assigned to no plant at all.
DEFAULT_ACTIONNERS = [
    {'name': "Lampe UV du balcon", 'act_on': "luminosity",
     'mqtt_topic': "bonjour-plant/balcon/lampe/set", 'plant': "Basilic du balcon", 'is_on': True},
    {'name': "Humidificateur de la serre", 'act_on': "humidity",
     'mqtt_topic': "bonjour-plant/serre/brumisateur/set", 'plant': "Tomates de la serre", 'is_on': False},
    {'name': "Tapis chauffant du jardin", 'act_on': "temperature",
     'mqtt_topic': "bonjour-plant/jardin/tapis/set", 'plant': "Fraisier du jardin", 'is_on': True},
    {'name': "Prise de rechange", 'act_on': "humidity",
     'mqtt_topic': "bonjour-plant/atelier/prise/set", 'plant': None, 'is_on': False},
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

        for sensor in DEFAULT_SENSORS:
            fields = dict(sensor)
            plant_name = fields.pop('plant')
            fields['plant'] = GrowingPlant.objects.filter(display_name=plant_name).first() if plant_name else None
            _, created = Sensor.objects.get_or_create(name=fields['name'], defaults=fields)
            if created:
                logger.info("Le capteur " + fields['name'] + " a été installé")

        for actionner in DEFAULT_ACTIONNERS:
            fields = dict(actionner)
            plant_name = fields.pop('plant')
            fields['plant'] = GrowingPlant.objects.filter(display_name=plant_name).first() if plant_name else None
            if fields['is_on']:
                fields['last_switch'] = datetime.datetime.now() - datetime.timedelta(hours=6)
            _, created = Actionner.objects.get_or_create(name=fields['name'], defaults=fields)
            if created:
                logger.info("L'actionneur " + fields['name'] + " a été installé")

        self.stdout.write(self.style.SUCCESS("Plant types, growing plants, sensors and actionners are set up."))
