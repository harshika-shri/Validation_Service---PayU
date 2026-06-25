from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from src.data.clients.postgres_client import (
    get_session_factory,
)
from src.messaging.post_commit import (
    discard_pending_validation_events,
    publish_committed_validation_events,
)

T = TypeVar("T")


async def run_with_db_session(
    handler: Callable[
        [AsyncSession],
        Awaitable[T],
    ],
) -> T:
    session_factory = get_session_factory()

    async with session_factory() as session:
        try:
            result = await handler(
                session,
            )
            await session.commit()
            publish_committed_validation_events()

            return result
        except Exception:
            await session.rollback()
            discard_pending_validation_events()
            raise


def run_async_in_worker(
    handler: Callable[
        [AsyncSession],
        Awaitable[T],
    ],
) -> T:
    return asyncio.run(
        run_with_db_session(
            handler,
        ),
    )
