from __future__ import annotations

import logging
from uuid import UUID

from src.control.agents.po_resolution.line_allocation_search import (
    LineMatchEdge,
)
from src.core.exceptions.llm_exc import LLMServiceError
from src.data.models.postgres.enums import AllocationMatchType
from src.data.repositories.line_item_validation.invoice_line_item_repository import (
    InvoiceLineItemRecord,
)
from src.data.repositories.po_resolution.po_line_item_repository import (
    POLineItemRecord,
)
from src.utils.llm_client import (
    compare_line_items_semantically,
)
from src.utils.po_line_matching_utils import (
    has_text,
    normalize_item_code,
    normalize_item_description,
)

logger = logging.getLogger(
    __name__,
)


class POLineMatcher:
    def __init__(
        self,
    ) -> None:
        self._semantic_cache: dict[
            tuple[str, str],
            bool,
        ] = {}

    async def build_match_edges(
        self,
        invoice_lines: list[InvoiceLineItemRecord],
        po_lines: list[POLineItemRecord],
    ) -> dict[UUID, list[UUID]]:
        typed_edges = await self.build_typed_match_edges(
            invoice_lines=invoice_lines,
            po_lines=po_lines,
        )

        return {
            invoice_line_id: [
                edge.po_line_id
                for edge in edges
            ]
            for invoice_line_id, edges in typed_edges.items()
        }

    async def build_typed_match_edges(
        self,
        invoice_lines: list[InvoiceLineItemRecord],
        po_lines: list[POLineItemRecord],
    ) -> dict[UUID, list[LineMatchEdge]]:
        edges: dict[UUID, list[LineMatchEdge]] = {}

        for invoice_line in invoice_lines:
            matching_edges: list[LineMatchEdge] = []

            for po_line in po_lines:
                match_type = await self._resolve_match_type(
                    invoice_line=invoice_line,
                    po_line=po_line,
                )

                if match_type is not None:
                    matching_edges.append(
                        LineMatchEdge(
                            po_line_id=po_line.id,
                            match_type=match_type,
                        ),
                    )

            edges[
                invoice_line.id
            ] = matching_edges

        return edges

    async def _resolve_match_type(
        self,
        invoice_line: InvoiceLineItemRecord,
        po_line: POLineItemRecord,
    ) -> AllocationMatchType | None:
        if self._match_by_item_code(
            invoice_line.item_code,
            po_line.item_code,
        ):
            return AllocationMatchType.EXACT_CODE

        if self._match_by_item_code(
            invoice_line.hsn_sac_code,
            po_line.item_code,
        ):
            return AllocationMatchType.EXACT_CODE

        if self._match_by_description(
            invoice_line.item_description,
            po_line.item_description,
        ):
            return AllocationMatchType.EXACT_CODE

        if await self._match_by_semantic_description(
            invoice_line.item_description,
            po_line.item_description,
        ):
            return AllocationMatchType.LLM_FUZZY

        return None

    async def _lines_match(
        self,
        invoice_line: InvoiceLineItemRecord,
        po_line: POLineItemRecord,
    ) -> bool:
        return (
            await self._resolve_match_type(
                invoice_line=invoice_line,
                po_line=po_line,
            )
            is not None
        )

    @staticmethod
    def _match_by_item_code(
        invoice_code: str | None,
        po_code: str | None,
    ) -> bool:
        if not has_text(
            invoice_code,
        ) or not has_text(
            po_code,
        ):
            return False

        assert invoice_code is not None
        assert po_code is not None

        return normalize_item_code(
            invoice_code,
        ) == normalize_item_code(
            po_code,
        )

    @staticmethod
    def _match_by_description(
        invoice_description: str | None,
        po_description: str | None,
    ) -> bool:
        if not has_text(
            invoice_description,
        ) or not has_text(
            po_description,
        ):
            return False

        assert invoice_description is not None
        assert po_description is not None

        return normalize_item_description(
            invoice_description,
        ) == normalize_item_description(
            po_description,
        )

    async def _match_by_semantic_description(
        self,
        invoice_description: str | None,
        po_description: str | None,
    ) -> bool:
        if not has_text(
            invoice_description,
        ) or not has_text(
            po_description,
        ):
            return False

        assert invoice_description is not None
        assert po_description is not None

        cache_key = (
            normalize_item_description(
                invoice_description,
            ),
            normalize_item_description(
                po_description,
            ),
        )

        if cache_key in self._semantic_cache:
            return self._semantic_cache[
                cache_key
            ]

        try:
            match_result = compare_line_items_semantically(
                extracted=invoice_description,
                master=po_description,
            )
        except LLMServiceError:
            logger.exception(
                "LLM line item comparison failed",
            )
            self._semantic_cache[
                cache_key
            ] = False
            return False

        self._semantic_cache[
            cache_key
        ] = match_result.is_match

        return match_result.is_match
