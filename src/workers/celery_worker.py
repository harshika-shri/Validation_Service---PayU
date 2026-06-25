from __future__ import annotations

import logging

from src.config.celery import celery_app

import src.tasks.validation_tasks  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

__all__ = [
    "celery_app",
]
