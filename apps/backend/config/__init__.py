# Importa a instância do Celery para que o Django a encontre automaticamente.
from .celery import app as celery_app

__all__ = ("celery_app",)
