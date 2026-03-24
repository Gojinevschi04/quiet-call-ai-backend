"""Standalone task execution for the scheduler worker.

Creates its own DB session and dependencies to avoid
sharing state with the scheduler polling session.
"""

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import engine
from app.core.logging import get_logger

logger = get_logger(__name__)


async def execute_due_task(task_id: int, user_id: int) -> None:
    """Execute a single task using the configured call manager with a fresh DB session."""
    from app.core.config import settings
    from app.integrations.call_manager import CallManager
    from app.integrations.realtime_call_manager import RealtimeCallManager
    from app.modules.calls.repository import CallSessionRepository, LogLineRepository
    from app.modules.tasks.repository import TaskRepository
    from app.modules.templates.repository import TemplateRepository
    from app.modules.users.repository import UserRepository

    async with AsyncSession(engine) as session:
        repos = {
            "task_repository": TaskRepository(session=session),
            "template_repository": TemplateRepository(session=session),
            "call_session_repository": CallSessionRepository(session=session),
            "log_line_repository": LogLineRepository(session=session),
            "user_repository": UserRepository(session=session),
        }
        manager = RealtimeCallManager(**repos) if settings.USE_REALTIME_API else CallManager(**repos)

        try:
            result = await manager.execute_task(task_id, user_id)
            logger.info("Task %d auto-executed with status: %s", task_id, result.status)
        except Exception as task_error:
            logger.error("Task %d auto-execution failed: %s", task_id, str(task_error))
