from collections.abc import Sequence
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.files.models import File
from app.modules.files.repository import FileRepository
from app.modules.files.schema import FileType


@pytest.mark.asyncio
async def test_create(mock_session: MagicMock, mock_file: File) -> None:
    mock_session.refresh = AsyncMock()

    repo = FileRepository(session=mock_session)
    result = await repo.create(mock_file)

    mock_session.add.assert_called_once_with(mock_file)
    mock_session.commit.assert_called_once()
    assert result == mock_file


@pytest.mark.asyncio
async def test_get_by_id(mock_session: MagicMock, mock_file: File) -> None:
    mock_result = MagicMock()
    mock_result.first.return_value = mock_file
    mock_session.exec.return_value = mock_result

    repo = FileRepository(session=mock_session)
    result = await repo.get_by_id(1, 1)

    assert result == mock_file


@pytest.mark.asyncio
async def test_get_by_id_not_found(mock_session: MagicMock) -> None:
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_session.exec.return_value = mock_result

    repo = FileRepository(session=mock_session)
    result = await repo.get_by_id(999, 1)

    assert result is None


@pytest.mark.asyncio
async def test_get_by_hash(mock_session: MagicMock, mock_file: File) -> None:
    mock_result = MagicMock()
    mock_result.first.return_value = mock_file
    mock_session.exec.return_value = mock_result

    repo = FileRepository(session=mock_session)
    result = await repo.get_by_hash("abc123", 1)

    assert result == mock_file


@pytest.mark.asyncio
async def test_update(mock_session: MagicMock, mock_file: File) -> None:
    mock_session.refresh = AsyncMock()

    repo = FileRepository(session=mock_session)
    result = await repo.update(mock_file)

    mock_session.commit.assert_called_once()
    assert result == mock_file


@pytest.mark.asyncio
async def test_delete_success(mock_session: MagicMock, mock_file: File) -> None:
    mock_result = MagicMock()
    mock_result.first.return_value = mock_file
    mock_session.exec.return_value = mock_result
    mock_session.delete = AsyncMock()

    repo = FileRepository(session=mock_session)
    result = await repo.delete(1, 1)

    assert result is True
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_delete_not_found(mock_session: MagicMock) -> None:
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_session.exec.return_value = mock_result

    repo = FileRepository(session=mock_session)
    result = await repo.delete(999, 1)

    assert result is False


@pytest.mark.asyncio
async def test_get_all_by_user(mock_session: MagicMock) -> None:
    files = [
        File(
            id=i,
            filename=f"file{i}.pdf",
            original_filename=f"file{i}.pdf",
            file_path=f"/path/file{i}.pdf",
            file_size=1024,
            file_type=FileType.PDF,
            user_id=1,
        )
        for i in range(3)
    ]
    mock_result = MagicMock()
    mock_result.all.return_value = files
    mock_session.exec.return_value = mock_result

    repo = FileRepository(session=mock_session)
    result = await repo.get_all_by_user(user_id=1)

    assert isinstance(result, Sequence)
    assert len(result) == 3


@pytest.mark.asyncio
async def test_get_all_by_user_empty_for_other_user(mock_session: MagicMock) -> None:
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_session.exec.return_value = mock_result

    repo = FileRepository(session=mock_session)
    result = await repo.get_all_by_user(user_id=999)

    assert len(result) == 0
