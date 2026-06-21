from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from src.data.models.postgres.enums import IssueDecisionCategory
from src.data.models.postgres.issue_decision_rules import IssueDecisionRule
from src.data.repositories.base_repo import BaseRepository


@dataclass(frozen=True, slots=True)
class DecisionRuleRecord:
    issue_code: str
    decision_category: IssueDecisionCategory
    description: str | None
    is_active: bool


class IssueDecisionRulesRepository(BaseRepository):
    @staticmethod
    def _normalize_category(
        value: str,
    ) -> IssueDecisionCategory:
        normalized = value.strip().casefold()

        if normalized in {
            "approve",
            "approved",
        }:
            return IssueDecisionCategory.APPROVE

        if normalized in {
            "partial_approve",
            "partial approve",
        }:
            return IssueDecisionCategory.PARTIAL_APPROVE

        if normalized in {
            "reject",
            "rejected",
        }:
            return IssueDecisionCategory.REJECT

        return IssueDecisionCategory(
            normalized,
        )

    async def get_decision_category(
        self,
        issue_code: str,
    ) -> IssueDecisionCategory | None:
        stmt = (
            select(
                IssueDecisionRule.decision_category,
            )
            .where(
                IssueDecisionRule.issue_code == issue_code,
                IssueDecisionRule.is_active.is_(
                    True,
                ),
            )
            .limit(
                1,
            )
        )

        result = await self.execute(
            stmt,
        )
        value = result.scalar_one_or_none()

        if value is None:
            return None

        return self._normalize_category(
            value,
        )

    async def get_all_decision_rules(
        self,
    ) -> list[DecisionRuleRecord]:
        stmt = (
            select(
                IssueDecisionRule.issue_code,
                IssueDecisionRule.decision_category,
                IssueDecisionRule.description,
                IssueDecisionRule.is_active,
            )
            .where(
                IssueDecisionRule.is_active.is_(
                    True,
                ),
            )
            .order_by(
                IssueDecisionRule.issue_code,
            )
        )

        result = await self.execute(
            stmt,
        )

        return [
            DecisionRuleRecord(
                issue_code=row.issue_code,
                decision_category=self._normalize_category(
                    row.decision_category,
                ),
                description=row.description,
                is_active=row.is_active,
            )
            for row in result.all()
        ]
