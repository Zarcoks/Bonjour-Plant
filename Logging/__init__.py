"""
Logging package: the object creating the application log records.

The application reaches its own logger through the application object:

    from core.app import app

    app.logger.info("ma log")
"""
from .levels import DEBUG, ERROR, INFO, LEVELS, STDLIB_LEVELS, WARNING
from .logger import Logger, ROOT_MODULE

__all__ = [
    'Logger',
    'ROOT_MODULE',
    'LEVELS',
    'STDLIB_LEVELS',
    'DEBUG',
    'INFO',
    'WARNING',
    'ERROR',
]
