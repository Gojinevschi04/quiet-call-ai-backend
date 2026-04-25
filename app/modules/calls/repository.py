from collections.abc import Sequence
from datetime import datetime

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

    async def get_usage_for_user(self, user_id: int) -> dict[str, int]:
        """Sum token counts + call duration across all call sessions owned by a user (via their tasks)."""
        from app.modules.tasks.models import Task

        result = await self._session.exec(
            select(
                func.coalesce(func.sum(CallSession.input_audio_tokens), 0),
                func.coalesce(func.sum(CallSession.output_audio_tokens), 0),
                func.coalesce(func.sum(CallSession.input_text_tokens), 0),
                func.coalesce(func.sum(CallSession.output_text_tokens), 0),
                func.count(CallSession.id),
                func.coalesce(func.sum(CallSession.duration), 0),
            )
            .select_from(CallSession)
            .join(Task, Task.id == CallSession.task_id)
            .where(Task.user_id == user_id)
        )
        input_audio, output_audio, input_text, output_text, call_count, duration_sec = result.one()
        return {
            "input_audio_tokens": int(input_audio),
            "output_audio_tokens": int(output_audio),
            "input_text_tokens": int(input_text),
            "output_text_tokens": int(output_text),
            "call_count": int(call_count),
            "duration_seconds": int(duration_sec),
        }

    async def get_monthly_usage_per_user(
        self, since: datetime
    ) -> Sequence[tuple[int, str, int, int, int, int, int, int]]:
        """Aggregate per-user call stats since a given datetime.

        Returns rows of (user_id, user_email, call_count, total_duration_sec,
        input_audio, output_audio, input_text, output_text).
        """
        from app.modules.tasks.models import Task
        from app.modules.users.models import User

        result = await self._session.exec(
            select(
                User.id,
                User.email,
                func.count(CallSession.id),
                func.coalesce(func.sum(CallSession.duration), 0),
                func.coalesce(func.sum(CallSession.input_audio_tokens), 0),
                func.coalesce(func.sum(CallSession.output_audio_tokens), 0),
                func.coalesce(func.sum(CallSession.input_text_tokens), 0),
                func.coalesce(func.sum(CallSession.output_text_tokens), 0),
            )
            .select_from(CallSession)
            .join(Task, Task.id == CallSession.task_id)
            .join(User, User.id == Task.user_id)
            .where(CallSession.created_at >= since)
            .group_by(User.id, User.email)
            .order_by(func.coalesce(func.sum(CallSession.duration), 0).desc())
        )
        return result.all()


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
        # Sort by id (insertion order) instead of timestamp — timestamps are the moment
        # OpenAI events arrive, which can be out-of-order because Whisper user transcription
        # completes asynchronously (often after the next agent turn's transcript is done).
        # Rows are inserted in conversation order (see get_ordered_transcript), so id
        # preserves the real back-and-forth sequence.
        result = await self._session.exec(
            select(LogLine).where(LogLine.session_id == session_id).order_by(LogLine.id)
        )
        return result.all()
