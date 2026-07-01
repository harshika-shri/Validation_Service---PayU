from __future__ import annotations

import logging

from celery.signals import worker_process_init

import src.tasks.validation_tasks  # noqa: F401
from src.config.celery import celery_app
from src.control.graph.checkpointer import reset_checkpointer_globals
from src.data.clients.postgres_client import reset_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


@worker_process_init.connect
def _reset_worker_state_after_fork(
    **kwargs: object,
) -> None:
    reset_engine()
    reset_checkpointer_globals()


__all__ = [
    "celery_app",
]
