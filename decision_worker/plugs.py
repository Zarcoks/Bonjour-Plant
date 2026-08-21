"""Writing on the plugs what a decision has decided."""
from django.utils import timezone

from core.app import app

logger = app.module_logger("decisions")


def switch(actionner, on, decision):
    """
    Sets the state wanted of a plug, and answers whether that changed anything.

    A decision writes here and nowhere else: the MQTT worker is the one that
    then tells the plug. `decision` names, in the journal, the decision that
    asked for the switch.
    """
    if actionner.is_on == on:
        return False
    actionner.is_on = on
    actionner.last_switch = timezone.now()
    actionner.save(update_fields=['is_on', 'last_switch'])
    logger.info(decision + " : l'actionneur " + actionner.name + " est "
                + ("allumé" if on else "éteint") + " pour la plante "
                + (actionner.plant.display_name if actionner.plant else "sans plante"))
    return True
