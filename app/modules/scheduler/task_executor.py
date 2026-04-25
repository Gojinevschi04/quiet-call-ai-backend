"""Standalone task execution for the scheduler worker.

Creates its own DB session and dependencies to avoid
sharing state with the scheduler polling session.
"""

from app.core.database import async_session
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
    # Use the shared factory (expire_on_commit=False) so attribute access on ORM
    # instances after commit doesn't trigger a lazy-load — async SQLAlchemy can't
    # lazy-load in arbitrary contexts and fails with MissingGreenlet.
    async with semaphore, async_session() as session:
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
                "Task %d: forcing legacy path after prior realtime init failure",
                task_id,
            )
            use_realtime = False

        manager = RealtimeCallManager(**repos) if use_realtime else CallManager(**repos)

        try:
            result = await manager.execute_task(task_id, user_id)
            # Access status via a try/except — instance may be expired after the
            # session commits in execute_task (in which case attribute access would
            # trigger a lazy reload and fail in async context).
            try:
                result_status = result.status
            except Exception:
                result_status = "executed (status refresh skipped)"
            logger.info("Task %d auto-executed with status: %s", task_id, result_status)
        except Exception:
            logger.exception("Task %d auto-execution failed", task_id)
            # Mark the task FAILED so it doesn't stay SCHEDULED forever — the scheduler
            # janitor handles stuck IN_PROGRESS, but a pre-claim failure leaves the task
            # as-is. Explicitly flip to FAILED with the error reason.
            try:
                from app.modules.tasks.schema import TaskStatus

                current = await task_repo.get_by_id_any_user(task_id)
                if current and current.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                    current.status = TaskStatus.FAILED
                    current.error_reason = "Auto-execution error (see worker logs)"
                    await task_repo.update(current)
            except Exception:
                logger.exception("Failed to mark task %d as FAILED after error", task_id)
