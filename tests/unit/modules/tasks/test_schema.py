from datetime import datetime, timedelta

import pytest

from app.modules.tasks.schema import TaskCreate, TaskEditRequest


def _future_dt_at_hour(hour: int) -> datetime:
    return (datetime.now() + timedelta(days=3)).replace(hour=hour, minute=0, second=0, microsecond=0)


def test_task_create_accepts_scheduled_time_within_window() -> None:
    task_data = TaskCreate(
        target_phone="+37312345678",
        template_id=1,
        slot_data={},
        scheduled_time=_future_dt_at_hour(10).isoformat(),
    )
    assert task_data.scheduled_time is not None


def test_task_create_rejects_scheduled_time_before_window() -> None:
    with pytest.raises(ValueError, match="call hours"):
        TaskCreate(
            target_phone="+37312345678",
            template_id=1,
            slot_data={},
            scheduled_time=_future_dt_at_hour(3).isoformat(),
        )


def test_task_create_rejects_scheduled_time_after_window() -> None:
    with pytest.raises(ValueError, match="call hours"):
        TaskCreate(
            target_phone="+37312345678",
            template_id=1,
            slot_data={},
            scheduled_time=_future_dt_at_hour(22).isoformat(),
        )


def test_task_create_rejects_scheduled_time_in_past() -> None:
    past_time = datetime.now() - timedelta(hours=1)
    with pytest.raises(ValueError, match="must be in the future"):
        TaskCreate(
            target_phone="+37312345678",
            template_id=1,
            slot_data={},
            scheduled_time=past_time.isoformat(),
        )


def test_task_edit_accepts_scheduled_time_within_window() -> None:
    edit_data = TaskEditRequest(scheduled_time=_future_dt_at_hour(15).isoformat())
    assert edit_data.scheduled_time is not None


def test_task_edit_rejects_scheduled_time_outside_window() -> None:
    with pytest.raises(ValueError, match="call hours"):
        TaskEditRequest(scheduled_time=_future_dt_at_hour(2).isoformat())


def test_task_create_rejects_boundary_hour_at_end() -> None:
    """hour == CALL_WINDOW_END_HOUR (default 20) should be rejected (exclusive upper bound)."""
    with pytest.raises(ValueError, match="call hours"):
        TaskCreate(
            target_phone="+37312345678",
            template_id=1,
            slot_data={},
            scheduled_time=_future_dt_at_hour(20).isoformat(),
        )


def test_task_create_accepts_boundary_hour_at_start() -> None:
    """hour == CALL_WINDOW_START_HOUR (default 9) should be accepted (inclusive lower bound)."""
    task_data = TaskCreate(
        target_phone="+37312345678",
        template_id=1,
        slot_data={},
        scheduled_time=_future_dt_at_hour(9).isoformat(),
    )
    assert task_data.scheduled_time is not None


# --- _validate_slot_value: garbage/injection rejection ---


@pytest.mark.parametrize(
    "bad_value",
    [
        "lalala",
        "aaaa",
        "xxxxxx",
        "a",
        "line1\nline2",
        "{{ignore_prev}}",
        "\x00bad",
    ],
)
def test_task_create_rejects_garbage_slot_value(bad_value: str) -> None:
    with pytest.raises(ValueError):
        TaskCreate(
            target_phone="+37312345678",
            template_id=1,
            slot_data={"preferred_date": bad_value},
        )


@pytest.mark.parametrize(
    "good_value",
    [
        "R-48291",
        "John Smith",
        "2026-05-10",
        "+37312345678",
        "Appointment at 10 AM",
    ],
)
def test_task_create_accepts_realistic_slot_value(good_value: str) -> None:
    task_data = TaskCreate(
        target_phone="+37312345678",
        template_id=1,
        slot_data={"preferred_date": good_value},
    )
    assert task_data.slot_data["preferred_date"] == good_value


def test_task_create_rejects_scheduled_more_than_90_days_future() -> None:
    """Regression: `scheduled_time` must be ≤ 90 days in the future."""
    from datetime import datetime, timedelta
    from app.modules.tasks.schema import TaskCreate
    import pytest

    too_far = (datetime.now() + timedelta(days=91)).replace(hour=10, minute=0, second=0, microsecond=0)
    with pytest.raises(Exception, match="90 days"):
        TaskCreate(
            target_phone="+37312345678",
            template_id=1,
            slot_data={},
            scheduled_time=too_far,
        )


def test_task_create_accepts_scheduled_within_90_days() -> None:
    from datetime import datetime, timedelta
    from app.modules.tasks.schema import TaskCreate

    ok = (datetime.now() + timedelta(days=89)).replace(hour=10, minute=0, second=0, microsecond=0)
    task = TaskCreate(
        target_phone="+37312345678",
        template_id=1,
        slot_data={},
        scheduled_time=ok,
    )
    assert task.scheduled_time == ok
