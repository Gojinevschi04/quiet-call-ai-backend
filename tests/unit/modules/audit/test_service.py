from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.audit.models import AuditLog
from app.modules.audit.repository import AuditLogRepository
from app.modules.audit.service import AuditService, record_audit


@pytest.fixture
def mock_audit_entries() -> list[AuditLog]:
    now = datetime.now()
    return [
        AuditLog(
            id=1,
            user_id=2,
            action="task.create",
            target_type="task",
            target_id=10,
            details=None,
            created_at=now,
            updated_at=now,
        ),
        AuditLog(
            id=2,
            user_id=3,
            action="task.cancel",
            target_type="task",
            target_id=11,
            details="Cancelled",
            created_at=now,
            updated_at=now,
        ),
    ]


# --- AuditService.list_entries ---


@pytest.mark.asyncio
async def test_list_entries_returns_paginated_results(mock_audit_entries: list[AuditLog]) -> None:
    mock_audit_repo = MagicMock(spec=AuditLogRepository)
    mock_audit_repo.get_all_paginated = AsyncMock(return_value=(mock_audit_entries, 2))

    service = AuditService(audit_repository=mock_audit_repo)
    items, total = await service.list_entries()

    assert items == mock_audit_entries
    assert total == 2
    mock_audit_repo.get_all_paginated.assert_called_once_with(50, 0)


@pytest.mark.asyncio
async def test_list_entries_forwards_limit_and_offset(mock_audit_entries: list[AuditLog]) -> None:
    mock_audit_repo = MagicMock(spec=AuditLogRepository)
    mock_audit_repo.get_all_paginated = AsyncMock(return_value=(mock_audit_entries[:1], 5))

    service = AuditService(audit_repository=mock_audit_repo)
    items, total = await service.list_entries(limit=1, offset=3)

    assert len(items) == 1
    assert total == 5
    mock_audit_repo.get_all_paginated.assert_called_once_with(1, 3)


@pytest.mark.asyncio
async def test_list_entries_empty() -> None:
    mock_audit_repo = MagicMock(spec=AuditLogRepository)
    mock_audit_repo.get_all_paginated = AsyncMock(return_value=([], 0))

    service = AuditService(audit_repository=mock_audit_repo)
    items, total = await service.list_entries()

    assert items == []
    assert total == 0


# --- record_audit helper ---


def _build_session_context(session_mock: MagicMock) -> MagicMock:
    """Build an async-context-manager factory that yields ``session_mock``."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session_mock)
    ctx.__aexit__ = AsyncMock(return_value=None)
    factory = MagicMock(return_value=ctx)
    return factory


@pytest.mark.asyncio
async def test_record_audit_writes_entry_to_db() -> None:
    session_mock = MagicMock()
    session_mock.add = MagicMock()
    session_mock.commit = AsyncMock()
    session_mock.refresh = AsyncMock()

    session_factory = _build_session_context(session_mock)

    with patch("app.modules.audit.service.async_session", session_factory):
        await record_audit(
            user_id=1,
            action="task.create",
            target_type="task",
            target_id=42,
            details="Created",
        )

    session_factory.assert_called_once()
    session_mock.add.assert_called_once()
    added_entry = session_mock.add.call_args.args[0]
    assert isinstance(added_entry, AuditLog)
    assert added_entry.user_id == 1
    assert added_entry.action == "task.create"
    assert added_entry.target_type == "task"
    assert added_entry.target_id == 42
    assert added_entry.details == "Created"
    session_mock.commit.assert_awaited_once()
    session_mock.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_record_audit_with_optional_fields_defaulting_to_none() -> None:
    session_mock = MagicMock()
    session_mock.add = MagicMock()
    session_mock.commit = AsyncMock()
    session_mock.refresh = AsyncMock()

    session_factory = _build_session_context(session_mock)

    with patch("app.modules.audit.service.async_session", session_factory):
        await record_audit(user_id=None, action="system.event", target_type="system")

    added_entry = session_mock.add.call_args.args[0]
    assert added_entry.user_id is None
    assert added_entry.target_id is None
    assert added_entry.details is None


@pytest.mark.asyncio
async def test_record_audit_swallows_db_errors() -> None:
    session_mock = MagicMock()
    session_mock.add = MagicMock()
    session_mock.commit = AsyncMock(side_effect=RuntimeError("db down"))
    session_mock.refresh = AsyncMock()

    session_factory = _build_session_context(session_mock)

    with patch("app.modules.audit.service.async_session", session_factory):
        # Must not raise — fire-and-forget swallows the exception.
        await record_audit(user_id=1, action="task.create", target_type="task")


@pytest.mark.asyncio
async def test_record_audit_logs_exception_on_failure() -> None:
    session_mock = MagicMock()
    session_mock.add = MagicMock()
    session_mock.commit = AsyncMock(side_effect=RuntimeError("boom"))
    session_mock.refresh = AsyncMock()

    session_factory = _build_session_context(session_mock)

    with (
        patch("app.modules.audit.service.async_session", session_factory),
        patch("app.modules.audit.service.logger") as mock_logger,
    ):
        await record_audit(user_id=5, action="task.retry", target_type="task")

    mock_logger.exception.assert_called_once()


@pytest.mark.asyncio
async def test_record_audit_swallows_session_open_errors() -> None:
    # If async_session() itself raises, record_audit should still not raise.
    def _exploding_factory() -> None:
        raise RuntimeError("cannot connect")

    with patch("app.modules.audit.service.async_session", side_effect=_exploding_factory):
        await record_audit(user_id=1, action="task.create", target_type="task")
