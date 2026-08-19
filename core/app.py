"""
The application object: the single access path to the services shared by the
whole application.

    from core.app import app

    app.logger.info("ma log")
"""
from Logging import Logger


class Application:
    """Holds the application wide services. Instantiated once, as `app` below."""

    def __init__(self):
        self.logger = Logger()

    def module_logger(self, name):
        """A logger tagged with a page or module name, e.g. app.module_logger('plant_types')."""
        return self.logger.module(name)


app = Application()
