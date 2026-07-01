from __future__ import annotations

import logging
import time
import traceback
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.celery import celery_app
from src.config.settings import settings
from src.core.services.validation_workflow_service import (
    ValidationWorkflowService,
)
from src.schemas.validation_state_schema import (
    ValidationStateSchema,
)
from src.messaging.redis_stream_ack import (
    acknowledge_extraction_stream_message,
)
from src.utils.celery_async import run_async_in_worker
from src.utils.transient_errors import (
    is_permanent_business_error,
    is_transient_error,
)

logger = logging.getLogger(
    "validation.tasks",
)


def _retry_countdown(
    retries: int,
) -> int:
    return settings.CELERY_TASK_RETRY_BACKOFF_SECONDS * (
        2**retries
    )


def _log_task_received(
    task_name: str,
    task_id: str,
    **context: object,
) -> float:
    logger.info(
        "Task received name=%s task_id=%s context=%s",
        task_name,
        task_id,
        context,
    )

    return time.monotonic()


def _log_task_started(
    task_name: str,
    task_id: str,
) -> None:
    logger.info(
        "Task started name=%s task_id=%s",
        task_name,
        task_id,
    )


def _log_task_completed(
    task_name: str,
    task_id: str,
    *,
    started_at: float,
    result: dict[str, Any],
) -> None:
    duration = time.monotonic() - started_at
    logger.info(
        "Task completed name=%s task_id=%s duration=%.2fs result=%s",
        task_name,
        task_id,
        duration,
        result,
    )


def _log_task_failed(
    task_name: str,
    task_id: str,
    *,
    started_at: float,
    error: BaseException,
) -> None:
    duration = time.monotonic() - started_at
    logger.error(
        "Task failed name=%s task_id=%s duration=%.2fs reason=%s",
        task_name,
        task_id,
        duration,
        error,
    )
    traceback.print_exc()


def _log_task_retried(
    task_name: str,
    task_id: str,
    *,
    retries: int,
    error: BaseException,
) -> None:
    logger.warning(
        "Task retried name=%s task_id=%s attempt=%s reason=%s",
        task_name,
        task_id,
        retries + 1,
        error,
    )


def _failure_result(
    *,
    reason: str,
    invoice_id: str,
) -> dict[str, str | None]:
    return {
        "status": "failed",
        "reason": reason,
        "invoice_id": invoice_id,
        "task_id": None,
    }


def _serialize_validation_result(
    schema: ValidationStateSchema,
    *,
    task_id: str,
) -> dict[str, str | None]:
    return {
        "status": "completed",
        "task_id": task_id,
        "invoice_id": str(
            schema.invoice_id,
        ),
        "decision": (
            schema.decision.value
            if schema.decision is not None
            else None
        ),
        "flow_outcome": schema.flow_outcome.value,
        "invoice_status": (
            schema.invoice_status.value
            if schema.invoice_status is not None
            else None
        ),
    }


async def _run_invoice_validation(
    session: AsyncSession,
    *,
    invoice_id: UUID,
    skip_if_already_completed: bool = False,
    force_fresh: bool = False,
) -> ValidationStateSchema:
    service = ValidationWorkflowService(
        session,
    )

    return await service.run_invoice_validation(
        invoice_id=invoice_id,
        skip_if_already_completed=skip_if_already_completed,
        force_fresh=force_fresh,
    )


def _maybe_acknowledge_stream_message(
    *,
    stream_message_id: str | None,
    invoice_id: str,
) -> None:
    if stream_message_id is None:
        return

    acknowledge_extraction_stream_message(
        message_id=stream_message_id,
        invoice_id=invoice_id,
    )


@celery_app.task(
    bind=True,
    name="src.tasks.validation_tasks.validate_invoice",
    max_retries=settings.CELERY_TASK_MAX_RETRIES,
    acks_late=True,
)
def validate_invoice(
    self,
    invoice_id: str,
    *,
    skip_if_already_completed: bool = False,
    force_fresh: bool = False,
    stream_message_id: str | None = None,
) -> dict[str, str | None]:
    task_name = "validate_invoice"
    started_at = _log_task_received(
        task_name,
        self.request.id,
        invoice_id=invoice_id,
        stream_message_id=stream_message_id,
    )

    try:
        _log_task_started(
            task_name,
            self.request.id,
        )

        schema = run_async_in_worker(
            lambda session: _run_invoice_validation(
                session,
                invoice_id=UUID(
                    invoice_id,
                ),
                skip_if_already_completed=skip_if_already_completed,
                force_fresh=force_fresh,
            ),
        )

        result = _serialize_validation_result(
            schema,
            task_id=self.request.id,
        )

        _log_task_completed(
            task_name,
            self.request.id,
            started_at=started_at,
            result=result,
        )

        _maybe_acknowledge_stream_message(
            stream_message_id=stream_message_id,
            invoice_id=invoice_id,
        )

        return result
    except Exception as error:
        if is_permanent_business_error(
            error,
        ):
            _log_task_failed(
                task_name,
                self.request.id,
                started_at=started_at,
                error=error,
            )

            reason = str(
                error,
            )

            if hasattr(
                error,
                "detail",
            ):
                reason = str(
                    error.detail,
                )

            failure = _failure_result(
                reason=reason,
                invoice_id=invoice_id,
            )
            failure[
                "task_id"
            ] = self.request.id

            _maybe_acknowledge_stream_message(
                stream_message_id=stream_message_id,
                invoice_id=invoice_id,
            )

            return failure

        if (
            is_transient_error(
                error,
            )
            and self.request.retries
            < settings.CELERY_TASK_MAX_RETRIES
        ):
            _log_task_retried(
                task_name,
                self.request.id,
                retries=self.request.retries,
                error=error,
            )
            raise self.retry(
                exc=error,
                countdown=_retry_countdown(
                    self.request.retries,
                ),
            ) from error

        _log_task_failed(
            task_name,
            self.request.id,
            started_at=started_at,
            error=error,
        )

        if (
            stream_message_id is not None
            and self.request.retries >= settings.CELERY_TASK_MAX_RETRIES
        ):
            _maybe_acknowledge_stream_message(
                stream_message_id=stream_message_id,
                invoice_id=invoice_id,
            )

        raise
