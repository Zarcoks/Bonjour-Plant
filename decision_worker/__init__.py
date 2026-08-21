"""
The worker taking the decisions the application makes on its own.

Each decision reads the state of the plants and writes what it wants of the
actionners; the MQTT worker is the one that then tells the plugs. Keeping the
two apart means a decision is a database write, and nothing more.

For now there is one: `light_the_plants`, which follows the light window of each
plant whose light is left to the application.
"""
from .light import light_the_plants

__all__ = ['light_the_plants']
