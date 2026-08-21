"""
The worker checking that the installation adds up.

An actionner is believed on its word twice over: the state it reports, which the
MQTT worker reads as it arrives, and the effect it is supposed to have, which
only the measures can tell. `check_the_actionners` looks at the second: a plug
that is off while what it acts on climbs, or on while it does not move, is
warned about the same way a plug that belies its state is.

Nothing is switched here. What the plugs do is the user's business — the worker
only says what does not add up.
"""
from .checks import check_the_actionners, drift_of

__all__ = ['check_the_actionners', 'drift_of']
