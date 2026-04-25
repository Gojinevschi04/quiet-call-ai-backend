from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.calls.models import CallSession, LogLine
from app.modules.calls.repository import CallSessionRepository, LogLineRepository

# --- CallSessionRepository ---


@pytest.mark.asyncio
async def test_create_session(mock_session: MagicMock, mock_call_session: CallSession) -> None:
    repo = CallSessionRepository(session=mock_session)
    result = await repo.create(mock_call_session)

    mock_session.add.assert_called_once_with(mock_call_session)
    mock_session.commit.assert_called_once()
    assert result == mock_call_session


@pytest.mark.asyncio
async def test_create_session_refresh(mock_session: MagicMock, mock_call_session: CallSession) -> None:
    repo = CallSessionRepository(session=mock_session)
    await repo.create(mock_call_session)

    mock_session.refresh.assert_called_once_with(mock_call_session)


@pytest.mark.asyncio
async def test_get_by_task_id(mock_session: MagicMock, mock_call_session: CallSession) -> None:
    mock_result = MagicMock()
    mock_result.first.return_value = mock_call_session
    mock_session.exec = AsyncMock(return_value=mock_result)

    repo = CallSessionRepository(session=mock_session)
    result = await repo.get_by_task_id(1)

    assert result == mock_call_session


@pytest.mark.asyncio
async def test_get_by_task_id_not_found(mock_session: MagicMock) -> None:
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_session.exec = AsyncMock(return_value=mock_result)

    repo = CallSessionRepository(session=mock_session)
    result = await repo.get_by_task_id(999)

    assert result is None


@pytest.mark.asyncio
async def test_update_session(mock_session: MagicMock, mock_call_session: CallSession) -> None:
    repo = CallSessionRepository(session=mock_session)
    result = await repo.update(mock_call_session)

    mock_session.commit.assert_called_once()
    assert result == mock_call_session


@pytest.mark.asyncio
async def test_update_session_refresh(mock_session: MagicMock, mock_call_session: CallSession) -> None:
    repo = CallSessionRepository(session=mock_session)
    await repo.update(mock_call_session)

    mock_session.refresh.assert_called_once_with(mock_call_session)


@pytest.mark.asyncio
async def test_count_total(mock_session: MagicMock) -> None:
    mock_result = MagicMock()
    mock_result.one.return_value = 5
    mock_session.exec = AsyncMock(return_value=mock_result)

    repo = CallSessionRepository(session=mock_session)
    result = await repo.count_total()

    assert result == 5


@pytest.mark.asyncio
async def test_count_total_zero(mock_session: MagicMock) -> None:
    mock_result = MagicMock()
    mock_result.one.return_value = 0
    mock_session.exec = AsyncMock(return_value=mock_result)

    repo = CallSessionRepository(session=mock_session)
    result = await repo.count_total()

    assert result == 0


@pytest.mark.asyncio
async def test_get_usage_for_user_returns_aggregated_totals(mock_session: MagicMock) -> None:
    mock_result = MagicMock()
    mock_result.one.return_value = (1200, 3400, 800, 560, 4, 240)
    mock_session.exec = AsyncMock(return_value=mock_result)

    repo = CallSessionRepository(session=mock_session)
    totals = await repo.get_usage_for_user(user_id=1)

    assert totals == {
        "input_audio_tokens": 1200,
        "output_audio_tokens": 3400,
        "input_text_tokens": 800,
        "output_text_tokens": 560,
        "call_count": 4,
        "duration_seconds": 240,
    }


@pytest.mark.asyncio
async def test_get_usage_for_user_no_sessions_returns_zeros(mock_session: MagicMock) -> None:
    mock_result = MagicMock()
    mock_result.one.return_value = (0, 0, 0, 0, 0, 0)
    mock_session.exec = AsyncMock(return_value=mock_result)

    repo = CallSessionRepository(session=mock_session)
    totals = await repo.get_usage_for_user(user_id=999)

    assert totals["call_count"] == 0
    assert totals["input_audio_tokens"] == 0
    assert totals["duration_seconds"] == 0


# --- LogLineRepository ---


@pytest.mark.asyncio
async def test_create_log_line(mock_session: MagicMock, mock_log_lines: list[LogLine]) -> None:
    repo = LogLineRepository(session=mock_session)
    result = await repo.create(mock_log_lines[0])

    mock_session.add.assert_called_once_with(mock_log_lines[0])
    mock_session.commit.assert_called_once()
    assert result == mock_log_lines[0]


@pytest.mark.asyncio
async def test_create_log_line_refresh(mock_session: MagicMock, mock_log_lines: list[LogLine]) -> None:
    repo = LogLineRepository(session=mock_session)
    await repo.create(mock_log_lines[0])

    mock_session.refresh.assert_called_once_with(mock_log_lines[0])


@pytest.mark.asyncio
async def test_create_many(mock_session: MagicMock, mock_log_lines: list[LogLine]) -> None:
    repo = LogLineRepository(session=mock_session)
    result = await repo.create_many(mock_log_lines)

    assert mock_session.add.call_count == 2
    mock_session.commit.assert_called_once()
    assert len(result) == 2
    assert result[0] == mock_log_lines[0]
    assert result[1] == mock_log_lines[1]


@pytest.mark.asyncio
async def test_create_many_refresh_all(mock_session: MagicMock, mock_log_lines: list[LogLine]) -> None:
    repo = LogLineRepository(session=mock_session)
    await repo.create_many(mock_log_lines)

    assert mock_session.refresh.call_count == 2


@pytest.mark.asyncio
async def test_create_many_empty_list(mock_session: MagicMock) -> None:
    repo = LogLineRepository(session=mock_session)
    result = await repo.create_many([])

    mock_session.add.assert_not_called()
    mock_session.commit.assert_called_once()
    assert result == []


@pytest.mark.asyncio
async def test_get_by_session_id(mock_session: MagicMock, mock_log_lines: list[LogLine]) -> None:
    mock_result = MagicMock()
    mock_result.all.return_value = mock_log_lines
    mock_session.exec = AsyncMock(return_value=mock_result)

    repo = LogLineRepository(session=mock_session)
    result = await repo.get_by_session_id(1)

    assert len(result) == 2
    assert result[0].speaker == "agent"
    assert result[1].speaker == "interlocutor"


@pytest.mark.asyncio
async def test_get_by_session_id_sorts_by_id_not_timestamp(mock_session: MagicMock) -> None:
    """Regression: log lines must be ordered by id (insertion/conversation order), not
    by timestamp — timestamps reflect the moment an async OpenAI event arrived, which can
    be out-of-order when Whisper user transcription completes after the next agent turn."""
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_session.exec = AsyncMock(return_value=mock_result)

    repo = LogLineRepository(session=mock_session)
    await repo.get_by_session_id(1)

    rendered_sql = str(mock_session.exec.call_args[0][0]).lower()
    assert "order by log_line.id" in rendered_sql
    assert "order by log_line.timestamp" not in rendered_sql


@pytest.mark.asyncio
async def test_get_by_session_id_empty(mock_session: MagicMock) -> None:
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_session.exec = AsyncMock(return_value=mock_result)

    repo = LogLineRepository(session=mock_session)
    result = await repo.get_by_session_id(999)

    assert result == []


@pytest.mark.asyncio
async def test_get_by_session_id_returns_sequence(mock_session: MagicMock, mock_log_lines: list[LogLine]) -> None:
    mock_result = MagicMock()
    mock_result.all.return_value = mock_log_lines
    mock_session.exec = AsyncMock(return_value=mock_result)

    repo = LogLineRepository(session=mock_session)
    result = await repo.get_by_session_id(1)

    # Verify ordering fields are present
    assert result[0].text == "Hello, I'd like to make an appointment."
    assert result[1].text == "Sure, when would you like to come in?"
