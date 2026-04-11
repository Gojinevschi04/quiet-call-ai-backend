from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from app.modules.calls.exceptions import CallSessionNotFoundError
from app.modules.calls.schema import CallSessionResponse, LogLineResponse, TranscriptResponse
from app.modules.tasks.exceptions import TaskNotFoundError

# ---- Helper to build a TranscriptResponse ----

def _make_transcript(
    task_id: int = 1,
    duration: int | None = 120,
    lines: list[LogLineResponse] | None = None,
) -> TranscriptResponse:
    if lines is None:
        lines = [
            LogLineResponse(
                id=1,
                session_id=1,
                timestamp="2026-01-01T00:00:00",
                speaker="agent",
                text="Hello",
                detected_intent=None,
            ),
            LogLineResponse(
                id=2,
                session_id=1,
                timestamp="2026-01-01T00:00:08",
                speaker="interlocutor",
                text="Hi there",
                detected_intent="greeting",
            ),
        ]
    return TranscriptResponse(
        session=CallSessionResponse(
            id=1,
            task_id=task_id,
            start_time="2026-01-01T00:00:00",
            duration=duration,
            recording_uri="https://example.com/rec.wav",
            created_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:00",
        ),
        lines=lines,
    )


# ==============================================================
# GET /tasks/{task_id}/transcript  (JSON)
# ==============================================================


@pytest.mark.asyncio
async def test_get_transcript(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.calls.service.CallService.get_transcript") as mock_get:
        mock_get.return_value = _make_transcript()
        response = await authenticated_client.get("/tasks/1/transcript")
        assert response.status_code == 200
        data = response.json()
        assert len(data["lines"]) == 2
        assert data["session"]["duration"] == 120


@pytest.mark.asyncio
async def test_get_transcript_response_shape(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.calls.service.CallService.get_transcript") as mock_get:
        mock_get.return_value = _make_transcript()
        response = await authenticated_client.get("/tasks/1/transcript")
        data = response.json()

        session = data["session"]
        assert "id" in session
        assert "task_id" in session
        assert "start_time" in session
        assert "duration" in session
        assert "recording_uri" in session

        line = data["lines"][0]
        assert "id" in line
        assert "session_id" in line
        assert "timestamp" in line
        assert "speaker" in line
        assert "text" in line
        assert "detected_intent" in line


@pytest.mark.asyncio
async def test_get_transcript_empty_lines(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.calls.service.CallService.get_transcript") as mock_get:
        mock_get.return_value = _make_transcript(lines=[])
        response = await authenticated_client.get("/tasks/1/transcript")
        assert response.status_code == 200
        assert response.json()["lines"] == []


@pytest.mark.asyncio
async def test_get_transcript_task_not_found(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.calls.service.CallService.get_transcript") as mock_get:
        mock_get.side_effect = TaskNotFoundError("Not found")
        response = await authenticated_client.get("/tasks/999/transcript")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_transcript_no_session(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.calls.service.CallService.get_transcript") as mock_get:
        mock_get.side_effect = CallSessionNotFoundError("No session")
        response = await authenticated_client.get("/tasks/1/transcript")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_transcript_unauthenticated(client: AsyncClient) -> None:
    response = await client.get("/tasks/1/transcript")
    assert response.status_code == 401


# ==============================================================
# GET /tasks/{task_id}/transcript/download  (text file)
# ==============================================================


@pytest.mark.asyncio
async def test_download_transcript(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.calls.service.CallService.get_transcript") as mock_get:
        mock_get.return_value = TranscriptResponse(
            session=CallSessionResponse(
                id=1,
                task_id=5,
                start_time="2026-03-10T14:30:00",
                duration=95,
                recording_uri="https://example.com/rec.wav",
                created_at="2026-03-10T14:30:00",
                updated_at="2026-03-10T14:30:00",
            ),
            lines=[
                LogLineResponse(
                    id=1,
                    session_id=1,
                    timestamp="2026-03-10T14:30:05",
                    speaker="agent",
                    text="Hello, I am calling to schedule an appointment.",
                    detected_intent=None,
                ),
                LogLineResponse(
                    id=2,
                    session_id=1,
                    timestamp="2026-03-10T14:30:13",
                    speaker="interlocutor",
                    text="Sure, what date works for you?",
                    detected_intent="request_info",
                ),
            ],
        )
        response = await authenticated_client.get("/tasks/5/transcript/download")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]
        assert "transcript_task_5.txt" in response.headers["content-disposition"]

        text = response.text
        assert "Transcript — Task #5" in text
        assert "Duration: 1m 35s" in text
        assert "Agent:" in text
        assert "Caller:" in text
        assert "Hello, I am calling to schedule an appointment." in text
        assert "Sure, what date works for you?" in text


@pytest.mark.asyncio
async def test_download_transcript_no_duration(authenticated_client: AsyncClient) -> None:
    """When duration is None, the Duration line should not appear."""
    with patch("app.modules.calls.service.CallService.get_transcript") as mock_get:
        mock_get.return_value = _make_transcript(task_id=3, duration=None)
        response = await authenticated_client.get("/tasks/3/transcript/download")
        assert response.status_code == 200
        text = response.text
        assert "Duration:" not in text
        assert "Transcript — Task #3" in text


@pytest.mark.asyncio
async def test_download_transcript_zero_duration(authenticated_client: AsyncClient) -> None:
    """Duration of 0 is falsy, so Duration line should not appear."""
    with patch("app.modules.calls.service.CallService.get_transcript") as mock_get:
        mock_get.return_value = _make_transcript(duration=0)
        response = await authenticated_client.get("/tasks/1/transcript/download")
        text = response.text
        assert "Duration:" not in text


@pytest.mark.asyncio
async def test_download_transcript_empty_lines(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.calls.service.CallService.get_transcript") as mock_get:
        mock_get.return_value = _make_transcript(lines=[])
        response = await authenticated_client.get("/tasks/1/transcript/download")
        assert response.status_code == 200
        text = response.text
        assert "Transcript — Task #1" in text
        # Only header lines, no conversation lines
        assert "Agent:" not in text
        assert "Caller:" not in text


@pytest.mark.asyncio
async def test_download_transcript_speaker_mapping(authenticated_client: AsyncClient) -> None:
    """Agent speaker should display as 'Agent', interlocutor as 'Caller'."""
    with patch("app.modules.calls.service.CallService.get_transcript") as mock_get:
        mock_get.return_value = _make_transcript(lines=[
            LogLineResponse(
                id=1, session_id=1, timestamp="2026-01-01T00:00:00",
                speaker="agent", text="Line A", detected_intent=None,
            ),
            LogLineResponse(
                id=2, session_id=1, timestamp="2026-01-01T00:00:05",
                speaker="interlocutor", text="Line B", detected_intent=None,
            ),
        ])
        response = await authenticated_client.get("/tasks/1/transcript/download")
        text = response.text
        assert "Agent: Line A" in text
        assert "Caller: Line B" in text


@pytest.mark.asyncio
async def test_download_transcript_has_timestamps(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.calls.service.CallService.get_transcript") as mock_get:
        mock_get.return_value = _make_transcript()
        response = await authenticated_client.get("/tasks/1/transcript/download")
        text = response.text
        # Timestamps should be in [HH:MM:SS] format
        assert "[00:00:00]" in text


@pytest.mark.asyncio
async def test_download_transcript_not_found(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.calls.service.CallService.get_transcript") as mock_get:
        mock_get.side_effect = TaskNotFoundError("Not found")
        response = await authenticated_client.get("/tasks/999/transcript/download")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_download_transcript_no_session(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.calls.service.CallService.get_transcript") as mock_get:
        mock_get.side_effect = CallSessionNotFoundError("No session")
        response = await authenticated_client.get("/tasks/1/transcript/download")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_download_transcript_unauthenticated(client: AsyncClient) -> None:
    response = await client.get("/tasks/1/transcript/download")
    assert response.status_code == 401


# ==============================================================
# GET /tasks/{task_id}/session
# ==============================================================


@pytest.mark.asyncio
async def test_get_call_session(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.calls.service.CallService.get_session_by_task") as mock_get:
        mock_session = MagicMock()
        mock_session.id = 1
        mock_session.task_id = 1
        mock_session.start_time = "2026-01-01T00:00:00"
        mock_session.duration = 120
        mock_session.recording_uri = "https://example.com/rec.wav"
        mock_session.created_at = "2026-01-01T00:00:00"
        mock_session.updated_at = "2026-01-01T00:00:00"
        mock_get.return_value = mock_session

        response = await authenticated_client.get("/tasks/1/session")
        assert response.status_code == 200
        assert response.json()["duration"] == 120


@pytest.mark.asyncio
async def test_get_call_session_response_shape(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.calls.service.CallService.get_session_by_task") as mock_get:
        mock_session = MagicMock()
        mock_session.id = 1
        mock_session.task_id = 1
        mock_session.start_time = "2026-01-01T00:00:00"
        mock_session.duration = 120
        mock_session.recording_uri = "https://example.com/rec.wav"
        mock_session.created_at = "2026-01-01T00:00:00"
        mock_session.updated_at = "2026-01-01T00:00:00"
        mock_get.return_value = mock_session

        response = await authenticated_client.get("/tasks/1/session")
        data = response.json()
        assert set(data.keys()) == {
            "id", "task_id", "start_time", "duration",
            "recording_uri",
            "input_audio_tokens", "output_audio_tokens",
            "input_text_tokens", "output_text_tokens",
            "created_at", "updated_at",
        }


@pytest.mark.asyncio
async def test_get_call_session_null_fields(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.calls.service.CallService.get_session_by_task") as mock_get:
        mock_session = MagicMock()
        mock_session.id = 1
        mock_session.task_id = 1
        mock_session.start_time = "2026-01-01T00:00:00"
        mock_session.duration = None
        mock_session.recording_uri = None
        mock_session.created_at = "2026-01-01T00:00:00"
        mock_session.updated_at = "2026-01-01T00:00:00"
        mock_get.return_value = mock_session

        response = await authenticated_client.get("/tasks/1/session")
        data = response.json()
        assert data["duration"] is None
        assert data["recording_uri"] is None


@pytest.mark.asyncio
async def test_get_call_session_not_found(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.calls.service.CallService.get_session_by_task") as mock_get:
        mock_get.side_effect = TaskNotFoundError("Not found")
        response = await authenticated_client.get("/tasks/999/session")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_call_session_no_session(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.calls.service.CallService.get_session_by_task") as mock_get:
        mock_get.side_effect = CallSessionNotFoundError("No session")
        response = await authenticated_client.get("/tasks/1/session")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_call_session_unauthenticated(client: AsyncClient) -> None:
    response = await client.get("/tasks/1/session")
    assert response.status_code == 401


# ==============================================================
# GET /tasks/{task_id}/recording  (audio stream)
# ==============================================================


@pytest.mark.asyncio
async def test_download_recording_wav_inline(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.calls.service.CallService.get_recording_audio") as mock_get:
        mock_get.return_value = (b"RIFF" + b"\x00" * 100, "audio/wav")
        response = await authenticated_client.get("/tasks/1/recording")
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"
        assert "inline" in response.headers["content-disposition"]
        assert "recording_task_1.wav" in response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_download_recording_wav_as_attachment(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.calls.service.CallService.get_recording_audio") as mock_get:
        mock_get.return_value = (b"RIFF" + b"\x00" * 100, "audio/wav")
        response = await authenticated_client.get("/tasks/1/recording?download=true")
        assert response.status_code == 200
        assert "attachment" in response.headers["content-disposition"]
        assert "recording_task_1.wav" in response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_download_recording_mp3_inline(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.calls.service.CallService.get_recording_audio") as mock_get:
        mock_get.return_value = (b"\xff\xfb\x90\x00" + b"\x00" * 100, "audio/mpeg")
        response = await authenticated_client.get("/tasks/1/recording")
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/mpeg"
        assert "recording_task_1.mp3" in response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_download_recording_mp3_as_attachment(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.calls.service.CallService.get_recording_audio") as mock_get:
        mock_get.return_value = (b"\xff\xfb\x90\x00" + b"\x00" * 100, "audio/mpeg")
        response = await authenticated_client.get("/tasks/1/recording?download=true")
        assert response.status_code == 200
        assert "attachment" in response.headers["content-disposition"]
        assert "recording_task_1.mp3" in response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_download_recording_filename_includes_task_id(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.calls.service.CallService.get_recording_audio") as mock_get:
        mock_get.return_value = (b"RIFF" + b"\x00" * 10, "audio/wav")
        response = await authenticated_client.get("/tasks/42/recording")
        assert "recording_task_42.wav" in response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_download_recording_returns_audio_bytes(authenticated_client: AsyncClient) -> None:
    audio_data = b"RIFF" + b"\x00" * 200
    with patch("app.modules.calls.service.CallService.get_recording_audio") as mock_get:
        mock_get.return_value = (audio_data, "audio/wav")
        response = await authenticated_client.get("/tasks/1/recording")
        assert response.content == audio_data


@pytest.mark.asyncio
async def test_download_recording_not_found(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.calls.service.CallService.get_recording_audio") as mock_get:
        mock_get.side_effect = TaskNotFoundError("Not found")
        response = await authenticated_client.get("/tasks/999/recording")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_download_recording_no_session(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.calls.service.CallService.get_recording_audio") as mock_get:
        mock_get.side_effect = CallSessionNotFoundError("No session")
        response = await authenticated_client.get("/tasks/1/recording")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_download_recording_no_uri(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.calls.service.CallService.get_recording_audio") as mock_get:
        mock_get.side_effect = ValueError("No recording available")
        response = await authenticated_client.get("/tasks/1/recording")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_download_recording_unauthenticated(client: AsyncClient) -> None:
    response = await client.get("/tasks/1/recording")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_download_recording_default_is_inline(authenticated_client: AsyncClient) -> None:
    """Without ?download param, should default to inline."""
    with patch("app.modules.calls.service.CallService.get_recording_audio") as mock_get:
        mock_get.return_value = (b"RIFF" + b"\x00" * 10, "audio/wav")
        response = await authenticated_client.get("/tasks/1/recording")
        assert "inline" in response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_download_recording_download_false_is_inline(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.calls.service.CallService.get_recording_audio") as mock_get:
        mock_get.return_value = (b"RIFF" + b"\x00" * 10, "audio/wav")
        response = await authenticated_client.get("/tasks/1/recording?download=false")
        assert "inline" in response.headers["content-disposition"]
