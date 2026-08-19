"""The severities a log record can carry."""
import logging as stdlib_logging

DEBUG = "DEBUG"
INFO = "INFO"
WARNING = "WARNING"
ERROR = "ERROR"

# Ordered from the least to the most severe, as shown in the log page filter.
LEVELS = [DEBUG, INFO, WARNING, ERROR]

# The matching severity for the standard library logger writing on the console.
STDLIB_LEVELS = {
    DEBUG: stdlib_logging.DEBUG,
    INFO: stdlib_logging.INFO,
    WARNING: stdlib_logging.WARNING,
    ERROR: stdlib_logging.ERROR,
}
