from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.realtime_call_manager import RealtimeCallManager
from app.modules.tasks.models import Task
from app.modules.tasks.schema import TaskStatus
from app.modules.templates.models import DialogTemplate


def _make_manager_with_mocks() -> tuple[RealtimeCallManager, MagicMock, MagicMock, MagicMock]:
    task_repo = MagicMock()
    task_repo.get_by_id = AsyncMock()
    task_repo.get_by_id_any_user = AsyncMock()
    task_repo.update = AsyncMock()

    template_repo = MagicMock()
    template_repo.get_by_id = AsyncMock()

    call_session_repo = MagicMock()
    call_session_repo.create = AsyncMock()

    log_line_repo = MagicMock()
    user_repo = MagicMock()

    manager = RealtimeCallManager(
        task_repository=task_repo,
        template_repository=template_repo,
        call_session_repository=call_session_repo,
        log_line_repository=log_line_repo,
        user_repository=user_repo,
    )
    return manager, task_repo, template_repo, call_session_repo


def test_compute_ws_url_https_base() -> None:
    manager, *_ = _make_manager_with_mocks()
    with patch("app.core.config.settings.BASE_URL", "https://example.com"):
        assert manager._compute_ws_url() == "wss://example.com/ws/media-stream"


def test_compute_ws_url_http_base() -> None:
    manager, *_ = _make_manager_with_mocks()
    with patch("app.core.config.settings.BASE_URL", "http://localhost:8000"):
        assert manager._compute_ws_url() == "ws://localhost:8000/ws/media-stream"


def test_compute_ws_url_trailing_slash() -> None:
    manager, *_ = _make_manager_with_mocks()
    with patch("app.core.config.settings.BASE_URL", "https://example.com/"):
        assert manager._compute_ws_url() == "wss://example.com//ws/media-stream"


def test_escape_xml_replaces_all_special_chars() -> None:
    escaped = RealtimeCallManager._escape_xml('<tag attr="v">&\'</tag>')
    assert "<" not in escaped
    assert ">" not in escaped
    assert '"' not in escaped
    assert "'" not in escaped
    assert "&amp;" in escaped
    assert "&lt;" in escaped
    assert "&gt;" in escaped
    assert "&quot;" in escaped
    assert "&apos;" in escaped


def test_resolve_phone_with_override() -> None:
    manager, *_ = _make_manager_with_mocks()
    with patch("app.core.config.settings.TEST_PHONE_OVERRIDE", "+37360000000"):
        assert manager._resolve_phone("+19995551234") == "+37360000000"


def test_resolve_phone_without_override() -> None:
    manager, *_ = _make_manager_with_mocks()
    with patch("app.core.config.settings.TEST_PHONE_OVERRIDE", ""):
        assert manager._resolve_phone("+19995551234") == "+19995551234"


def test_build_stream_twiml_contains_all_parameters() -> None:
    manager, *_ = _make_manager_with_mocks()
    twiml = manager._build_stream_twiml(
        task_id=42,
        user_id=7,
        language="ro",
        system_prompt="You are Ana.",
        media_stream_ws_url="wss://example.com/ws/media-stream",
    )
    assert "<Connect>" in twiml
    assert 'url="wss://example.com/ws/media-stream"' in twiml
    assert 'name="task_id" value="42"' in twiml
    assert 'name="user_id" value="7"' in twiml
    assert 'name="language" value="ro"' in twiml
    assert "You are Ana." in twiml


def test_build_stream_twiml_escapes_system_prompt() -> None:
    manager, *_ = _make_manager_with_mocks()
    twiml = manager._build_stream_twiml(
        task_id=1,
        user_id=1,
        language="en",
        system_prompt='Prompt with "quotes" & <tags>.',
        media_stream_ws_url="wss://example.com/ws/media-stream",
    )
    assert '"quotes"' not in twiml
    assert "<tags>" not in twiml.replace("<Connect>", "").replace("<Response>", "").replace("<Stream", "")
    assert "&quot;" in twiml
    assert "&amp;" in twiml
    assert "&lt;tags&gt;" in twiml


@pytest.mark.asyncio
async def test_execute_task_not_found_raises() -> None:
    manager, task_repo, _, _ = _make_manager_with_mocks()
    task_repo.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match="not found"):
        await manager.execute_task(task_id=999, user_id=1)


@pytest.mark.asyncio
async def test_execute_task_wrong_status_raises() -> None:
    manager, task_repo, _, _ = _make_manager_with_mocks()
    existing_task = Task(
        id=1, target_phone="+37360000001", status=TaskStatus.COMPLETED,
        template_id=1, user_id=1, slot_data={},
    )
    task_repo.get_by_id = AsyncMock(return_value=existing_task)

    with pytest.raises(ValueError, match="cannot be executed"):
        await manager.execute_task(task_id=1, user_id=1)


@pytest.mark.asyncio
async def test_execute_task_template_missing_raises() -> None:
    manager, task_repo, template_repo, _ = _make_manager_with_mocks()
    existing_task = Task(
        id=1, target_phone="+37360000001", status=TaskStatus.PENDING,
        template_id=99, user_id=1, slot_data={},
    )
    task_repo.get_by_id = AsyncMock(return_value=existing_task)
    template_repo.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match="Template .* not found"):
        await manager.execute_task(task_id=1, user_id=1)


@pytest.mark.asyncio
async def test_execute_task_happy_path_marks_in_progress_and_initiates_call() -> None:
    manager, task_repo, template_repo, call_session_repo = _make_manager_with_mocks()
    existing_task = Task(
        id=1, target_phone="+37360000001", status=TaskStatus.PENDING,
        template_id=5, user_id=7, slot_data={"patient_name": "Ana"},
    )
    template = DialogTemplate(
        id=5, name="Make appointment", base_script="Book it.",
        required_slots=["patient_name"], language="en", is_active=True,
    )
    task_repo.get_by_id = AsyncMock(return_value=existing_task)
    template_repo.get_by_id = AsyncMock(return_value=template)

    manager._voice = MagicMock()
    manager._voice.initiate_call_with_twiml = AsyncMock(return_value="CA123")

    with patch("app.core.config.settings.BASE_URL", "https://example.com"), \
         patch("app.core.config.settings.TEST_PHONE_OVERRIDE", ""):
        result = await manager.execute_task(task_id=1, user_id=7)

    assert result.status == TaskStatus.IN_PROGRESS
    call_session_repo.create.assert_awaited_once()
    manager._voice.initiate_call_with_twiml.assert_awaited_once()
    call_args = manager._voice.initiate_call_with_twiml.call_args.kwargs
    assert call_args["to_phone"] == "+37360000001"
    assert "wss://example.com/ws/media-stream" in call_args["twiml"]


@pytest.mark.asyncio
async def test_execute_task_initiate_failure_marks_task_failed() -> None:
    manager, task_repo, template_repo, _ = _make_manager_with_mocks()
    existing_task = Task(
        id=1, target_phone="+37360000001", status=TaskStatus.PENDING,
        template_id=5, user_id=7, slot_data={},
    )
    template = DialogTemplate(
        id=5, name="T", base_script="x", required_slots=[], language="en", is_active=True,
    )
    task_repo.get_by_id = AsyncMock(return_value=existing_task)
    template_repo.get_by_id = AsyncMock(return_value=template)

    manager._voice = MagicMock()
    manager._voice.initiate_call_with_twiml = AsyncMock(side_effect=RuntimeError("Twilio down"))

    with patch("app.core.config.settings.BASE_URL", "https://example.com"):
        result = await manager.execute_task(task_id=1, user_id=7)

    assert result.status == TaskStatus.FAILED
    assert "Twilio down" in result.error_reason


@pytest.mark.asyncio
async def test_execute_task_admin_uses_any_user_lookup() -> None:
    manager, task_repo, template_repo, _ = _make_manager_with_mocks()
    existing_task = Task(
        id=1, target_phone="+37360000001", status=TaskStatus.PENDING,
        template_id=5, user_id=999, slot_data={},
    )
    template = DialogTemplate(
        id=5, name="T", base_script="x", required_slots=[], language="en", is_active=True,
    )
    task_repo.get_by_id_any_user = AsyncMock(return_value=existing_task)
    template_repo.get_by_id = AsyncMock(return_value=template)

    manager._voice = MagicMock()
    manager._voice.initiate_call_with_twiml = AsyncMock(return_value="CA123")

    with patch("app.core.config.settings.BASE_URL", "https://example.com"):
        await manager.execute_task(task_id=1, user_id=7, is_admin=True)

    task_repo.get_by_id_any_user.assert_awaited_once_with(1)
    task_repo.get_by_id.assert_not_called()
