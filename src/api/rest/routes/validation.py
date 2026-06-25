from uuid import UUID

from fastapi import APIRouter, status

from src.schemas.validation_task_schema import (
    ValidationTaskAcceptedResponse,
)
from src.tasks.validation_tasks import (
    validate_invoice,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["Validation"],
)


@router.post(
    "/validation/run/{invoice_id}",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ValidationTaskAcceptedResponse,
)
async def run_invoice_validation(
    invoice_id: UUID,
) -> ValidationTaskAcceptedResponse:
    task = validate_invoice.delay(
        invoice_id=str(
            invoice_id,
        ),
    )

    return ValidationTaskAcceptedResponse(
        task_id=task.id,
        invoice_id=invoice_id,
        status="queued",
    )


@router.post(
    "/validate/{invoice_id}",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ValidationTaskAcceptedResponse,
)
async def validate_invoice_route(
    invoice_id: UUID,
) -> ValidationTaskAcceptedResponse:
    task = validate_invoice.delay(
        invoice_id=str(
            invoice_id,
        ),
    )

    return ValidationTaskAcceptedResponse(
        task_id=task.id,
        invoice_id=invoice_id,
        status="queued",
    )
