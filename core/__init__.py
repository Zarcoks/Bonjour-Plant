# The Celery application is loaded with Django, so that the shared tasks and the
# worker signals are registered wherever the project is imported from.
from .celery import app as celery_app

__all__ = ['celery_app']
