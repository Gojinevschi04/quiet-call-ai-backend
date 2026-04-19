from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.audit.models import AuditLog
from app.modules.audit.repository import AuditLogRepository


@pytest.fixture
def mock_audit_entry() -> AuditLog:
    return AuditLog(
        id=1,
        user_id=2,
        action="task.create",
        target_type="task",
        target_id=42,
        details="Task created",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


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
            details="Cancelled by user",
            created_at=now,
            updated_at=now,
        ),
    ]


# --- create ---


@pytest.mark.asyncio
async def test_create_adds_entry_to_session(mock_session: MagicMock, mock_audit_entry: AuditLog) -> None:
    repo = AuditLogRepository(session=mock_session)
    result = await repo.create(mock_audit_entry)

    mock_session.add.assert_called_once_with(mock_audit_entry)
    mock_session.commit.assert_called_once()
    assert result == mock_audit_entry


@pytest.mark.asyncio
async def test_create_refreshes_entry(mock_session: MagicMock, mock_audit_entry: AuditLog) -> None:
    repo = AuditLogRepository(session=mock_session)
    await repo.create(mock_audit_entry)

    mock_session.refresh.assert_called_once_with(mock_audit_entry)


@pytest.mark.asyncio
async def test_create_returns_same_entry(mock_session: MagicMock, mock_audit_entry: AuditLog) -> None:
    repo = AuditLogRepository(session=mock_session)
    result = await repo.create(mock_audit_entry)

    assert result is mock_audit_entry


# --- get_all_paginated ---


@pytest.mark.asyncio
async def test_get_all_paginated_returns_items_and_total(
    mock_session: MagicMock, mock_audit_entries: list[AuditLog]
) -> None:
    items_result = MagicMock()
    items_result.all.return_value = mock_audit_entries
    count_result = MagicMock()
    count_result.one.return_value = 2
    mock_session.exec = AsyncMock(side_effect=[items_result, count_result])

    repo = AuditLogRepository(session=mock_session)
    items, total = await repo.get_all_paginated()

    assert items == mock_audit_entries
    assert total == 2


@pytest.mark.asyncio
async def test_get_all_paginated_empty_result(mock_session: MagicMock) -> None:
    items_result = MagicMock()
    items_result.all.return_value = []
    count_result = MagicMock()
    count_result.one.return_value = 0
    mock_session.exec = AsyncMock(side_effect=[items_result, count_result])

    repo = AuditLogRepository(session=mock_session)
    items, total = await repo.get_all_paginated()

    assert items == []
    assert total == 0


@pytest.mark.asyncio
async def test_get_all_paginated_returns_tuple(
    mock_session: MagicMock, mock_audit_entries: list[AuditLog]
) -> None:
    items_result = MagicMock()
    items_result.all.return_value = mock_audit_entries
    count_result = MagicMock()
    count_result.one.return_value = 2
    mock_session.exec = AsyncMock(side_effect=[items_result, count_result])

    repo = AuditLogRepository(session=mock_session)
    result = await repo.get_all_paginated()

    assert isinstance(result, tuple)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_all_paginated_default_pagination(
    mock_session: MagicMock, mock_audit_entries: list[AuditLog]
) -> None:
    items_result = MagicMock()
    items_result.all.return_value = mock_audit_entries
    count_result = MagicMock()
    count_result.one.return_value = 2
    mock_session.exec = AsyncMock(side_effect=[items_result, count_result])

    repo = AuditLogRepository(session=mock_session)
    await repo.get_all_paginated()

    # Two exec calls: one for the paginated select, one for the count
    assert mock_session.exec.call_count == 2


@pytest.mark.asyncio
async def test_get_all_paginated_custom_limit_offset(
    mock_session: MagicMock, mock_audit_entries: list[AuditLog]
) -> None:
    items_result = MagicMock()
    items_result.all.return_value = mock_audit_entries[:1]
    count_result = MagicMock()
    count_result.one.return_value = 10
    mock_session.exec = AsyncMock(side_effect=[items_result, count_result])

    repo = AuditLogRepository(session=mock_session)
    items, total = await repo.get_all_paginated(limit=1, offset=5)

    assert len(items) == 1
    assert total == 10


@pytest.mark.asyncio
async def test_get_all_paginated_total_reflects_full_count(mock_session: MagicMock) -> None:
    # Even when pagination limits items, total should reflect the full count.
    items_result = MagicMock()
    items_result.all.return_value = []
    count_result = MagicMock()
    count_result.one.return_value = 99
    mock_session.exec = AsyncMock(side_effect=[items_result, count_result])

    repo = AuditLogRepository(session=mock_session)
    items, total = await repo.get_all_paginated(limit=10, offset=1000)

    assert items == []
    assert total == 99
