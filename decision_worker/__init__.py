"""
The worker taking the decisions the application makes on its own.

Each decision reads the state of the plants and writes what it wants of the
actionners; the MQTT worker is the one that then tells the plugs. Keeping the
two apart means a decision is a database write, and nothing more.

There are two: `light_the_plants`, which follows the light window of each plant
whose light is left to the application, and `water_the_plants`, which follows
the humidity of each plant whose watering is left to it.
"""
from .light import light_the_plants
from .watering import water_the_plants

__all__ = ['light_the_plants', 'water_the_plants']
