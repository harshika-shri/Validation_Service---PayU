from typing import Any

from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.base import Executable


class BaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(self, stmt: Executable) -> Result[Any]:
        return await self.session.execute(stmt)
