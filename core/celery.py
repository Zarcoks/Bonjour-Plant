import os

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('bonjour_plant')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps, and from both workers.
app.autodiscover_tasks()
app.autodiscover_tasks(['mqtt_worker', 'sync_worker', 'decision_worker'], related_name='tasks')

app.conf.timezone = 'Europe/Paris'

# How often the measures of the sensors are written on the plants. Read from the
# environment rather than from the settings: the schedule is built at import
# time, before Django is ready.
PLANT_SYNC_SECONDS = int(os.environ.get("PLANT_SYNC_SECONDS", 30))

# How often we make sure somebody is still listening to the sensors.
MQTT_WATCH_SECONDS = int(os.environ.get("MQTT_WATCH_SECONDS", 60))

# How often the plugs are told the state they should be in.
ACTIONNER_SYNC_SECONDS = int(os.environ.get("ACTIONNER_SYNC_SECONDS", 60))

# How often the application takes its own decisions.
DECISION_SECONDS = int(os.environ.get("DECISION_SECONDS", 60))

app.conf.beat_schedule = {
    'sync_sensors_to_plants': {
        'task': 'sync_worker.sync_sensors_to_plants',
        'schedule': PLANT_SYNC_SECONDS,
    },
    'watch_the_mqtt_listening': {
        'task': 'mqtt_worker.watch_the_listening',
        'schedule': MQTT_WATCH_SECONDS,
    },
    'switch_the_plugs': {
        'task': 'mqtt_worker.switch_the_plugs',
        'schedule': ACTIONNER_SYNC_SECONDS,
    },
    'take_the_decisions': {
        'task': 'decision_worker.take_the_decisions',
        'schedule': DECISION_SECONDS,
    },
}
