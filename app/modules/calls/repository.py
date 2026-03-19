from collections.abc import Sequence

from sqlmodel import func, select

from app.core.repositories import Repository
from app.modules.calls.models import CallSession, LogLine


class CallSessionRepository(Repository):
    async def create(self, session: CallSession) -> CallSession:
        self._session.add(session)
        await self._session.commit()
        await self._session.refresh(session)
        return session

    async def get_by_task_id(self, task_id: int) -> CallSession | None:
        result = await self._session.exec(select(CallSession).where(CallSession.task_id == task_id))
        return result.first()

    async def update(self, session: CallSession) -> CallSession:
        await self._session.commit()
        await self._session.refresh(session)
        return session

    async def delete(self, session: CallSession) -> None:
        await self._session.delete(session)
        await self._session.commit()

    async def count_total(self) -> int:
        result = await self._session.exec(select(func.count()).select_from(CallSession))
        return result.one()


class LogLineRepository(Repository):
    async def create(self, log_line: LogLine) -> LogLine:
        self._session.add(log_line)
        await self._session.commit()
        await self._session.refresh(log_line)
        return log_line

    async def create_many(self, log_lines: list[LogLine]) -> list[LogLine]:
        for line in log_lines:
            self._session.add(line)
        await self._session.commit()
        for line in log_lines:
            await self._session.refresh(line)
        return log_lines

    async def delete_by_session_id(self, session_id: int) -> None:
        result = await self._session.exec(select(LogLine).where(LogLine.session_id == session_id))
        for line in result.all():
            await self._session.delete(line)
        await self._session.commit()

    async def get_by_session_id(self, session_id: int) -> Sequence[LogLine]:
        result = await self._session.exec(
            select(LogLine).where(LogLine.session_id == session_id).order_by(LogLine.timestamp)
        )
        return result.all()
