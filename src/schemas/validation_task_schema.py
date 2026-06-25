from uuid import UUID

from pydantic import BaseModel


class ValidationTaskAcceptedResponse(BaseModel):
    task_id: str
    invoice_id: UUID
    status: str
