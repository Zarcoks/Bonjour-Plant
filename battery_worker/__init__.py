"""
The worker watching the batteries of the sensors.

A sensor that runs out of batteries stops talking, and nothing else in the
application would notice: the measures simply stop arriving. `check_the_batteries`
looks at the charge each sensor last reported of itself and warns about those
whose batteries are worth changing.

This is not a question of coherence — nothing here is compared to anything else,
and no sensor is belied. It is the state of the installation itself, which is why
it lives in a worker of its own.

Nothing is written on the sensors. Changing batteries is the user's business —
the worker only says which ones are running out.
"""
from .checks import check_the_batteries, low_battery_message

__all__ = ['check_the_batteries', 'low_battery_message']
