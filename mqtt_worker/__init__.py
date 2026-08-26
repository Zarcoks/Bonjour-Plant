"""
The worker listening to the installation on the MQTT broker.

`SensorListener` holds the connection: it subscribes to the topics of the
registered sensors and of the actionners that report their state, records what
arrives, and keeps its subscriptions in step with the database.
The `listen_sensors` command runs it, in a container of its own: an endless loop
is not a Celery task, and Docker is the one that keeps a process alive.
"""
from . import feedback, state, switching, watering
from .broker import Broker, broker_from_url
from .listener import SensorListener

__all__ = ['Broker', 'broker_from_url', 'SensorListener', 'feedback', 'state', 'switching',
           'watering']
