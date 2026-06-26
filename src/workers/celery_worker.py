from __future__ import annotations

import logging

from celery.signals import worker_process_init

from src.config.celery import celery_app
from src.data.clients.postgres_client import reset_engine

import src.tasks.validation_tasks  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


@worker_process_init.connect
def _reset_db_engine_after_fork(
    **kwargs: object,
) -> None:
    reset_engine()


__all__ = [
    "celery_app",
]
