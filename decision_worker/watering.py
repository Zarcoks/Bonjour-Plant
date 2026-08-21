"""Deciding when the plants are to be watered."""
from plant_management.models import ACT_ON_HUMIDITY, GrowingPlant

from .plugs import switch

# How the switches of this decision read in the journal.
DECISION = "Arrosage automatique"


def humidity_wanted(plant_type):
    """
    The humidity a plant of that species is kept at: the middle of its range.

    Aiming at the middle rather than at the minimum leaves room on both sides —
    a plant watered up to its lower bound would be dry again at once.
    """
    return (plant_type.humidity_min + plant_type.humidity_max) / 2


def humidity_actionners_of(plant):
    """The plugs of that plant with something on them that adds humidity."""
    return plant.actionners.filter(is_deleted=False, act_on=ACT_ON_HUMIDITY)


def water_the_plants():
    """
    Waters the plants that have dried below what their species is kept at, and
    stops watering the others.

    Only the plants whose watering is left to the application are touched: one
    with `auto_watering` off is somebody else's business. A plant that has never
    reported its humidity counts as one that does not need water: nothing is
    left running on a measure we do not have.

    What is decided here is written on the actionners; the plugs are told by the
    MQTT worker.
    """
    summary = {'switched_on': 0, 'switched_off': 0}

    plants = (GrowingPlant.objects.filter(is_deleted=False, auto_watering=True)
              .select_related('plant_type'))
    for plant in plants:
        wanted = (plant.current_humidity is not None
                  and plant.current_humidity < humidity_wanted(plant.plant_type))
        for actionner in humidity_actionners_of(plant):
            if switch(actionner, wanted, DECISION):
                summary['switched_on' if wanted else 'switched_off'] += 1
    return summary
