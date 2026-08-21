"""Deciding when the plants are to be given light."""
from django.utils import timezone

from core.app import app
from plant_management.models import ACT_ON_LUMINOSITY, GrowingPlant

logger = app.module_logger("decisions")


def is_within(window_starts_at, window_ends_at, moment):
    """Whether that hour of the day falls in the window a plant wants light in."""
    return window_starts_at <= moment < window_ends_at


def light_actionners_of(plant):
    """The plugs of that plant with something on them that makes light."""
    return plant.actionners.filter(is_deleted=False, act_on=ACT_ON_LUMINOSITY)


def switch(actionner, on):
    """Sets the state wanted of a plug, and answers whether that changed anything."""
    if actionner.is_on == on:
        return False
    actionner.is_on = on
    actionner.last_switch = timezone.now()
    actionner.save(update_fields=['is_on', 'last_switch'])
    logger.info("Lumière automatique : l'actionneur " + actionner.name + " est "
                + ("allumé" if on else "éteint") + " pour la plante "
                + (actionner.plant.display_name if actionner.plant else "sans plante"))
    return True


def light_the_plants(at=None):
    """
    Gives light to the plants that are waiting for it, and takes it away from
    the others.

    Only the plants whose light is left to the application are touched: one with
    `auto_luminosity` off is somebody else's business. What is decided here is
    written on the actionners; the plugs are told by the MQTT worker.
    """
    moment = at or timezone.now().time()
    summary = {'switched_on': 0, 'switched_off': 0}

    plants = (GrowingPlant.objects.filter(is_deleted=False, auto_luminosity=True)
              .select_related('plant_type'))
    for plant in plants:
        wanted = is_within(plant.plant_type.light_starts_at, plant.plant_type.light_ends_at, moment)
        for actionner in light_actionners_of(plant):
            if switch(actionner, wanted):
                summary['switched_on' if wanted else 'switched_off'] += 1
    return summary
