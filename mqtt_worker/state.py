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

# Held by whoever is listening, or about to. Kept apart from the subscriptions:
# a listener that is starting, or retrying on a broker that does not answer, holds
# the listening without having a single topic to show yet.
ALIVE_KEY = 'mqtt:listener-alive'

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
    keep_alive()


def keep_alive():
    """Says the listening is still held, for a while longer."""
    cache.set(ALIVE_KEY, True, timeout=freshness_seconds())


def claim():
    """
    Takes the listening, unless somebody holds it already.

    Atomic, so that two schedulers cannot both start a listener: two listeners
    on the same topics would record every measure twice. Nobody ever hands the
    listening back — it is let go by not being kept alive, which is exactly what
    a killed process does.
    """
    return bool(cache.add(ALIVE_KEY, True, timeout=freshness_seconds()))


def is_taken():
    """Whether somebody is listening, or on their way to."""
    return cache.get(ALIVE_KEY) is not None


def read():
    """The subscriptions as last published, None when the worker is not talking."""
    return cache.get(CACHE_KEY)


def forget():
    """Drops the subscriptions: the worker is not listening any more."""
    cache.delete(CACHE_KEY)
