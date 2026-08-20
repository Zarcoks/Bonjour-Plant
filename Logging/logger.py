"""The application logger."""
import logging as stdlib_logging

from .levels import DEBUG, ERROR, INFO, STDLIB_LEVELS, WARNING

# The module name the application logger writes under.
ROOT_MODULE = "bonjour_plant"

# The app_log table the records are persisted into, as "<app>.<model>".
LOG_MODEL = "plant_management.AppLog"

# Longest message the app_log table accepts, see the AppLog model.
MESSAGE_MAX_LENGTH = 500


class Logger:
    """
    Creates log records: every call writes a line on the console and a row in
    the app_log table.

    A logger is bound to a module name, and derives sub-module loggers, so that
    the console output tells where a record comes from:

        logger = Logger()                       # module "bonjour_plant"
        page_logger = logger.module("plant_types")  # module "bonjour_plant.plant_types"
        page_logger.info("le type de plante Menthe a été créé")

    The application exposes one for the whole application, see `core.app.app`.
    """

    def __init__(self, module=ROOT_MODULE):
        self.module_name = module
        self.console = stdlib_logging.getLogger(module)

    def module(self, name):
        """Derives a logger writing under "<this module>.<name>"."""
        return Logger(module=self.module_name + "." + name)

    def debug(self, message, **fields):
        return self.log(DEBUG, message, **fields)

    def info(self, message, **fields):
        return self.log(INFO, message, **fields)

    def warning(self, message, **fields):
        return self.log(WARNING, message, **fields)

    def error(self, message, **fields):
        return self.log(ERROR, message, **fields)

    def log(self, level, message, **fields):
        """Writes one record, and returns the persisted AppLog row (None if it could not be saved)."""
        line = self.format(message, fields)
        self.console.log(STDLIB_LEVELS[level], line)
        return self.save(level, line)

    def format(self, message, fields):
        """Appends the extra fields to the message, as "message key=value"."""
        if not fields:
            return message
        return message + " " + " ".join("{}={}".format(key, value) for key, value in fields.items())

    def save(self, level, line):
        # The model is looked up here and not imported at module level: a logger
        # is usually built before Django has loaded its application registry.
        from django.apps import apps

        try:
            log_model = apps.get_model(LOG_MODEL)
            return log_model.objects.create(message=line[:MESSAGE_MAX_LENGTH], type=level)
        except Exception as error:
            # A log call must never break its caller, even without a database.
            self.console.warning("La log n'a pas pu être enregistrée : %s", error)
            return None
