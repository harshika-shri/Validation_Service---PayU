from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.rest.dependencies import get_db_session
from src.core.services.validation_workflow_service import (
    ValidationWorkflowService,
)
from src.schemas.validation_state_schema import ValidationStateSchema

router = APIRouter(
    prefix="/api/v1",
    tags=["Validation"],
)


@router.post(
    "/validation/run/{invoice_id}",
    status_code=status.HTTP_200_OK,
    response_model=ValidationStateSchema,
)
async def run_invoice_validation(
    invoice_id: UUID,
    db: AsyncSession = Depends(
        get_db_session,
    ),
) -> ValidationStateSchema:
    service = ValidationWorkflowService(
        session=db,
    )

    return await service.run_invoice_validation(
        invoice_id=invoice_id,
    )


@router.post(
    "/validate/{invoice_id}",
    status_code=status.HTTP_200_OK,
    response_model=ValidationStateSchema,
)
async def validate_invoice(
    invoice_id: UUID,
    db: AsyncSession = Depends(
        get_db_session,
    ),
) -> ValidationStateSchema:
    service = ValidationWorkflowService(
        session=db,
    )

    return await service.run_invoice_validation(
        invoice_id=invoice_id,
    )
