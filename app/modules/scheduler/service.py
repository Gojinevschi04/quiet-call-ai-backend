import asyncio
from datetime import datetime, timedelta

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import async_session
from app.core.logging import get_logger
from app.modules.tasks.models import Task
from app.modules.tasks.schema import TaskStatus

logger = get_logger(__name__)

POLL_INTERVAL_SECONDS = 30
RETRYABLE_ERROR_KEYWORDS = [
    "connection",
    "timeout",
    "network",
    "refused",
    "retries",
    "realtime_init_failed",
]
MAX_IN_PROGRESS_MINUTES = 10

MAX_RETRY_ATTEMPTS = 4
RETRY_BACKOFF_MINUTES = (1, 5, 30, 120)  # after attempt N, wait this many minutes


async def get_due_tasks(session: AsyncSession) -> list[tuple[int, int]]:
    """Find scheduled tasks past their scheduled_time."""
    result = await session.exec(
        select(Task.id, Task.user_id).where(
            Task.status == TaskStatus.SCHEDULED,
            Task.scheduled_time <= datetime.now(),
        )
    )
    return list(result.all())


async def get_retryable_failed_tasks(session: AsyncSession) -> list[tuple[int, int]]:
    """Find failed tasks with network-related errors eligible for auto-retry.

    Tasks are retried up to MAX_RETRY_ATTEMPTS times with exponential backoff:
    each attempt must wait until `next_retry_at` has passed before being picked up.
    """
    now = datetime.now()
    result = await session.exec(
        select(Task.id, Task.user_id, Task.error_reason, Task.retry_count, Task.next_retry_at).where(
            Task.status == TaskStatus.FAILED,
            Task.error_reason.isnot(None),
        )
    )
    retryable_tasks = []
    for task_id, user_id, error_reason, retry_count, next_retry_at in result.all():
        if not error_reason:
            continue
        if retry_count >= MAX_RETRY_ATTEMPTS:
            continue
        if next_retry_at is not None and next_retry_at > now:
            continue
        error_lower = error_reason.lower()
        if any(keyword in error_lower for keyword in RETRYABLE_ERROR_KEYWORDS):
            retryable_tasks.append((task_id, user_id))
    return retryable_tasks


async def mark_task_for_retry(session: AsyncSession, task_id: int) -> None:
    """Reset a failed task to PENDING for immediate retry, incrementing attempt count."""
    result = await session.exec(select(Task).where(Task.id == task_id))
    task = result.first()
    if task and task.status == TaskStatus.FAILED:
        original_error = task.error_reason or ""
        task.status = TaskStatus.PENDING
        task.retry_count += 1
        task.next_retry_at = None
        task.error_reason = original_error
        task.summary = None
        session.add(task)
        await session.commit()
        logger.info("Task %d reset for retry (attempt %d, was: %s)", task_id, task.retry_count, original_error[:100])


async def schedule_next_retry(session: AsyncSession, task_id: int) -> None:
    """Called when a task fails with a retryable error: schedule its next retry.

    Looks at the current retry_count to pick a backoff delay. If the task has
    already used all retry attempts, leaves it in FAILED without a next_retry_at.
    """
    now = datetime.now()
    result = await session.exec(select(Task).where(Task.id == task_id))
    task = result.first()
    if not task or task.status != TaskStatus.FAILED:
        return
    if task.retry_count >= MAX_RETRY_ATTEMPTS:
        task.next_retry_at = None
        session.add(task)
        await session.commit()
        return

    delay_minutes = RETRY_BACKOFF_MINUTES[min(task.retry_count, len(RETRY_BACKOFF_MINUTES) - 1)]
    task.next_retry_at = now + timedelta(minutes=delay_minutes)
    session.add(task)
    await session.commit()
    logger.info(
        "Task %d scheduled for retry in %d minutes (attempt %d/%d)",
        task_id,
        delay_minutes,
        task.retry_count + 1,
        MAX_RETRY_ATTEMPTS,
    )


async def transition_task(session: AsyncSession, task_id: int) -> None:
    """Transition a single task from SCHEDULED to PENDING."""
    result = await session.exec(select(Task).where(Task.id == task_id))
    task = result.first()
    if task and task.status == TaskStatus.SCHEDULED:
        task.status = TaskStatus.PENDING
        session.add(task)
        await session.commit()
        logger.info("Task %d transitioned SCHEDULED → PENDING", task_id)


async def _process_due_tasks() -> None:
    """Find and execute all due scheduled tasks."""
    from app.modules.scheduler.task_executor import execute_due_task

    async with async_session() as session:
        due_tasks = await get_due_tasks(session)

    for task_id, user_id in due_tasks:
        try:
            async with async_session() as session:
                await transition_task(session, task_id)
            await execute_due_task(task_id, user_id)
        except Exception as process_error:
            logger.error("Failed to process task %d: %s", task_id, str(process_error))

    if due_tasks:
        logger.info("Processed %d due tasks", len(due_tasks))


async def _schedule_new_retry_windows() -> None:
    """For freshly-FAILED retryable tasks that have no next_retry_at yet, set one.

    Runs once per tick before _process_retryable_tasks, so a task failing at 10:00
    (say, with retry_count=0) gets next_retry_at=10:01 before we check for
    tasks due for retry.
    """
    async with async_session() as session:
        result = await session.exec(
            select(Task.id, Task.error_reason, Task.retry_count).where(
                Task.status == TaskStatus.FAILED,
                Task.error_reason.isnot(None),
                Task.next_retry_at.is_(None),
            )
        )
        for task_id, error_reason, retry_count in result.all():
            if not error_reason or retry_count >= MAX_RETRY_ATTEMPTS:
                continue
            if any(keyword in error_reason.lower() for keyword in RETRYABLE_ERROR_KEYWORDS):
                await schedule_next_retry(session, task_id)


async def _process_retryable_tasks() -> None:
    """Find and retry all failed tasks with network errors."""
    from app.modules.scheduler.task_executor import execute_due_task

    await _schedule_new_retry_windows()

    async with async_session() as session:
        retryable_tasks = await get_retryable_failed_tasks(session)

    for task_id, user_id in retryable_tasks:
        try:
            async with async_session() as session:
                await mark_task_for_retry(session, task_id)
            await execute_due_task(task_id, user_id)
        except Exception as retry_error:
            logger.error("Retry of task %d failed: %s", task_id, str(retry_error))

    if retryable_tasks:
        logger.info("Retried %d failed tasks", len(retryable_tasks))


async def _process_stuck_in_progress_tasks() -> None:
    """Flip tasks stuck at IN_PROGRESS for too long to FAILED.

    Happens when API restarts mid-call or the bridge crashes without running finalize.
    """
    cutoff = datetime.now() - timedelta(minutes=MAX_IN_PROGRESS_MINUTES)
    async with async_session() as session:
        result = await session.exec(
            select(Task).where(
                Task.status == TaskStatus.IN_PROGRESS,
                Task.updated_at <= cutoff,
            )
        )
        stuck = list(result.all())
        if not stuck:
            return

        for task in stuck:
            task.status = TaskStatus.FAILED
            task.error_reason = task.error_reason or (
                f"Stuck at IN_PROGRESS for over {MAX_IN_PROGRESS_MINUTES} minutes "
                "(likely interrupted by process restart or network failure)."
            )
            session.add(task)
        await session.commit()
        logger.warning("Marked %d stuck IN_PROGRESS tasks as FAILED", len(stuck))


async def run_scheduler() -> None:
    """Background polling loop for the worker process.

    Runs as a standalone process (app/worker.py), separate from the API.
    """
    logger.info("Task scheduler started (polling every %ds)", POLL_INTERVAL_SECONDS)

    while True:
        try:
            await _process_due_tasks()
            await _process_retryable_tasks()
            await _process_stuck_in_progress_tasks()
        except Exception as scheduler_error:
            logger.error("Scheduler error: %s", str(scheduler_error))

        await asyncio.sleep(POLL_INTERVAL_SECONDS)
