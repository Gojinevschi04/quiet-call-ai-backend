import asyncio
from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import engine
from app.core.logging import get_logger
from app.modules.tasks.models import Task
from app.modules.tasks.schema import TaskStatus

logger = get_logger(__name__)

POLL_INTERVAL_SECONDS = 30


RETRYABLE_ERROR_KEYWORDS = ["connection", "timeout", "network", "refused", "retries"]


async def get_due_tasks(session: AsyncSession) -> list[tuple[int, int]]:
    """Find scheduled tasks past their scheduled_time. Returns list of (task_id, user_id)."""
    now = datetime.now()
    result = await session.exec(
        select(Task.id, Task.user_id).where(
            Task.status == TaskStatus.SCHEDULED,
            Task.scheduled_time <= now,
        )
    )
    return list(result.all())


async def get_retryable_failed_tasks(session: AsyncSession) -> list[tuple[int, int]]:
    """Find failed tasks with network-related errors that should be auto-retried.

    Only retries tasks that failed due to transient network issues (connection,
    timeout, etc.), not business logic failures (rejection, cancelled by user).
    Tasks are retried once — if error_reason starts with '[RETRIED]', skip it.
    """
    result = await session.exec(
        select(Task.id, Task.user_id, Task.error_reason).where(
            Task.status == TaskStatus.FAILED,
            Task.error_reason.isnot(None),
        )
    )
    retryable = []
    for task_id, user_id, error_reason in result.all():
        if not error_reason or error_reason.startswith("[RETRIED]"):
            continue
        error_lower = error_reason.lower()
        if any(kw in error_lower for kw in RETRYABLE_ERROR_KEYWORDS):
            retryable.append((task_id, user_id))
    return retryable


async def mark_task_for_retry(session: AsyncSession, task_id: int) -> None:
    """Reset a failed task to PENDING for retry, marking it as retried."""
    result = await session.exec(select(Task).where(Task.id == task_id))
    task = result.first()
    if task and task.status == TaskStatus.FAILED:
        original_error = task.error_reason or ""
        task.status = TaskStatus.PENDING
        task.error_reason = f"[RETRIED] {original_error}"
        task.summary = None
        session.add(task)
        await session.commit()
        logger.info("Task %d reset for retry (was: %s)", task_id, original_error[:100])


async def transition_task(session: AsyncSession, task_id: int) -> None:
    """Transition a single task from SCHEDULED to PENDING."""
    result = await session.exec(select(Task).where(Task.id == task_id))
    task = result.first()
    if task and task.status == TaskStatus.SCHEDULED:
        task.status = TaskStatus.PENDING
        session.add(task)
        await session.commit()
        logger.info("Task %d transitioned SCHEDULED → PENDING", task_id)


async def run_scheduler() -> None:
    """Background loop that polls for due scheduled tasks.

    For each due task:
    1. Transitions SCHEDULED → PENDING
    2. Attempts auto-execution via CallManager

    This runs as a standalone process (app/worker.py), separate from the API.
    No Redis or Celery needed — simple asyncio polling.
    """
    logger.info("Task scheduler started (polling every %ds)", POLL_INTERVAL_SECONDS)

    while True:
        try:
            async with AsyncSession(engine) as session:
                due_tasks = await get_due_tasks(session)

            for task_id, user_id in due_tasks:
                try:
                    async with AsyncSession(engine) as session:
                        await transition_task(session, task_id)
                    await execute_due_task(task_id, user_id)

                except Exception as e:
                    logger.error("Failed to process task %d: %s", task_id, str(e))

            if due_tasks:
                logger.info("Processed %d due tasks", len(due_tasks))

            async with AsyncSession(engine) as session:
                retryable = await get_retryable_failed_tasks(session)

            for task_id, user_id in retryable:
                try:
                    async with AsyncSession(engine) as session:
                        await mark_task_for_retry(session, task_id)
                    await execute_due_task(task_id, user_id)
                except Exception as e:
                    logger.error("Retry of task %d failed: %s", task_id, str(e))

            if retryable:
                logger.info("Retried %d failed tasks", len(retryable))

        except Exception as e:
            logger.error("Scheduler error: %s", str(e))

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def execute_due_task(task_id: int, user_id: int) -> None:
    """Execute a due task using the CallManager.

    Creates its own DB session and dependencies to avoid
    sharing state with the scheduler session.
    """
    from app.integrations.call_manager import CallManager
    from app.modules.calls.repository import CallSessionRepository, LogLineRepository
    from app.modules.tasks.repository import TaskRepository
    from app.modules.templates.repository import TemplateRepository
    from app.modules.users.repository import UserRepository

    async with AsyncSession(engine) as session:
        task_repo = TaskRepository(session=session)
        template_repo = TemplateRepository(session=session)
        call_session_repo = CallSessionRepository(session=session)
        log_line_repo = LogLineRepository(session=session)
        user_repo = UserRepository(session=session)

        manager = CallManager(
            task_repository=task_repo,
            template_repository=template_repo,
            call_session_repository=call_session_repo,
            log_line_repository=log_line_repo,
            user_repository=user_repo,
        )

        try:
            result = await manager.execute_task(task_id, user_id)
            logger.info("Task %d auto-executed with status: %s", task_id, result.status)
        except Exception as e:
            logger.error("Task %d auto-execution failed: %s", task_id, str(e))
