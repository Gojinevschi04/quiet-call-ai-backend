"""Standalone task execution for the scheduler worker.

Creates its own DB session and dependencies to avoid
sharing state with the scheduler polling session.
"""

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import engine
from app.core.logging import get_logger

logger = get_logger(__name__)


REALTIME_INIT_FAILED_MARKER = "[REALTIME_INIT_FAILED]"


async def execute_due_task(task_id: int, user_id: int) -> None:
    """Execute a single task using the configured call manager with a fresh DB session.

    Gated by the process-local call semaphore so worker-triggered calls
    respect the same MAX_CONCURRENT_CALLS cap as API-triggered ones.

    If the task's last attempt failed during realtime init, force the legacy
    path for this retry so we don't keep hitting the same broken endpoint.
    """
    from app.core.concurrency import get_call_semaphore
    from app.core.config import settings
    from app.integrations.call_manager import CallManager
    from app.integrations.realtime_call_manager import RealtimeCallManager
    from app.modules.calls.repository import CallSessionRepository, LogLineRepository
    from app.modules.tasks.repository import TaskRepository
    from app.modules.templates.repository import TemplateRepository
    from app.modules.users.repository import UserRepository

    semaphore = get_call_semaphore()
    async with semaphore, AsyncSession(engine) as session:
        task_repo = TaskRepository(session=session)
        repos = {
            "task_repository": task_repo,
            "template_repository": TemplateRepository(session=session),
            "call_session_repository": CallSessionRepository(session=session),
            "log_line_repository": LogLineRepository(session=session),
            "user_repository": UserRepository(session=session),
        }

        task = await task_repo.get_by_id_any_user(task_id)
        use_realtime = settings.USE_REALTIME_API
        if use_realtime and task and task.error_reason and REALTIME_INIT_FAILED_MARKER in task.error_reason:
            logger.info(
                "Task %d: forcing legacy path after prior realtime init failure", task_id,
            )
            use_realtime = False

        manager = RealtimeCallManager(**repos) if use_realtime else CallManager(**repos)

        try:
            result = await manager.execute_task(task_id, user_id)
            logger.info("Task %d auto-executed with status: %s", task_id, result.status)
        except Exception as task_error:
            logger.error("Task %d auto-execution failed: %s", task_id, str(task_error))
