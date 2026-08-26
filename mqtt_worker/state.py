"""
What the MQTT worker tells the rest of the application about itself.

The worker lives in another process: it leaves what it listens to in the cache,
and the pages read it from there. The entry is short-lived on purpose — a worker
that stopped talking stops being reported as listening.
"""
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

CACHE_KEY = 'mqtt:subscriptions'

# How many synchronisations an entry survives without being written again.
FRESHNESS_FACTOR = 3


def freshness_seconds():
    return settings.MQTT_SYNC_SECONDS * FRESHNESS_FACTOR


def publish(broker, topics):
    """Leaves the subscriptions where the pages can read them."""
    cache.set(CACHE_KEY, {
        'broker': str(broker),
        'topics': sorted(topics),
        'at': timezone.now(),
    }, timeout=freshness_seconds())



def read():
    """The subscriptions as last published, None when the worker is not talking."""
    return cache.get(CACHE_KEY)


def forget():
    """Drops the subscriptions: the worker is not listening any more."""
    cache.delete(CACHE_KEY)
