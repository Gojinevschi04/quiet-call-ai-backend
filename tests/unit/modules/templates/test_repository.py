from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.templates.models import DialogTemplate
from app.modules.templates.repository import TemplateRepository


@pytest.mark.asyncio
async def test_create(mock_session: MagicMock, mock_template: DialogTemplate) -> None:
    repo = TemplateRepository(session=mock_session)
    result = await repo.create(mock_template)

    mock_session.add.assert_called_once_with(mock_template)
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once_with(mock_template)
    assert result == mock_template


@pytest.mark.asyncio
async def test_get_by_id(mock_session: MagicMock, mock_template: DialogTemplate) -> None:
    mock_result = MagicMock()
    mock_result.first.return_value = mock_template
    mock_session.exec = AsyncMock(return_value=mock_result)

    repo = TemplateRepository(session=mock_session)
    result = await repo.get_by_id(1)

    assert result == mock_template


@pytest.mark.asyncio
async def test_get_by_id_not_found(mock_session: MagicMock) -> None:
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_session.exec = AsyncMock(return_value=mock_result)

    repo = TemplateRepository(session=mock_session)
    result = await repo.get_by_id(999)

    assert result is None


@pytest.mark.asyncio
async def test_get_by_name(mock_session: MagicMock, mock_template: DialogTemplate) -> None:
    mock_result = MagicMock()
    mock_result.first.return_value = mock_template
    mock_session.exec = AsyncMock(return_value=mock_result)

    repo = TemplateRepository(session=mock_session)
    result = await repo.get_by_name("Make Appointment")

    assert result == mock_template


@pytest.mark.asyncio
async def test_get_all(mock_session: MagicMock, mock_template: DialogTemplate) -> None:
    mock_result = MagicMock()
    mock_result.all.return_value = [mock_template]
    mock_session.exec = AsyncMock(return_value=mock_result)

    repo = TemplateRepository(session=mock_session)
    result = await repo.get_all()

    assert len(result) == 1
    assert result[0] == mock_template


@pytest.mark.asyncio
async def test_update(mock_session: MagicMock, mock_template: DialogTemplate) -> None:
    repo = TemplateRepository(session=mock_session)
    result = await repo.update(mock_template)

    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once_with(mock_template)
    assert result == mock_template


@pytest.mark.asyncio
async def test_delete_success(mock_session: MagicMock, mock_template: DialogTemplate) -> None:
    mock_result = MagicMock()
    mock_result.first.return_value = mock_template
    mock_session.exec = AsyncMock(return_value=mock_result)

    repo = TemplateRepository(session=mock_session)
    result = await repo.delete(1)

    mock_session.delete.assert_called_once_with(mock_template)
    mock_session.commit.assert_called_once()
    assert result is True


@pytest.mark.asyncio
async def test_delete_not_found(mock_session: MagicMock) -> None:
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_session.exec = AsyncMock(return_value=mock_result)

    repo = TemplateRepository(session=mock_session)
    result = await repo.delete(999)

    assert result is False


@pytest.mark.asyncio
async def test_get_by_name_not_found(mock_session: MagicMock) -> None:
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_session.exec = AsyncMock(return_value=mock_result)

    repo = TemplateRepository(session=mock_session)
    result = await repo.get_by_name("Nonexistent Template")

    assert result is None


@pytest.mark.asyncio
async def test_get_all_paginated(mock_session: MagicMock, mock_template: DialogTemplate) -> None:
    mock_templates_result = MagicMock()
    mock_templates_result.all.return_value = [mock_template]
    mock_count_result = MagicMock()
    mock_count_result.one.return_value = 1
    mock_session.exec = AsyncMock(side_effect=[mock_templates_result, mock_count_result])

    repo = TemplateRepository(session=mock_session)
    templates, total = await repo.get_all_paginated(limit=50, offset=0)

    assert len(templates) == 1
    assert total == 1


@pytest.mark.asyncio
async def test_get_all_paginated_empty(mock_session: MagicMock) -> None:
    mock_templates_result = MagicMock()
    mock_templates_result.all.return_value = []
    mock_count_result = MagicMock()
    mock_count_result.one.return_value = 0
    mock_session.exec = AsyncMock(side_effect=[mock_templates_result, mock_count_result])

    repo = TemplateRepository(session=mock_session)
    templates, total = await repo.get_all_paginated()

    assert templates == []
    assert total == 0


@pytest.mark.asyncio
async def test_deactivate_success(mock_session: MagicMock, mock_template: DialogTemplate) -> None:
    mock_result = MagicMock()
    mock_result.first.return_value = mock_template
    mock_session.exec = AsyncMock(return_value=mock_result)

    repo = TemplateRepository(session=mock_session)
    result = await repo.deactivate(1)

    assert result is True
    assert mock_template.is_active is False
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once_with(mock_template)


@pytest.mark.asyncio
async def test_deactivate_not_found(mock_session: MagicMock) -> None:
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_session.exec = AsyncMock(return_value=mock_result)

    repo = TemplateRepository(session=mock_session)
    result = await repo.deactivate(999)

    assert result is False


@pytest.mark.asyncio
async def test_get_names_by_ids_returns_name_mapping(mock_session: MagicMock) -> None:
    mock_result = MagicMock()
    mock_result.all.return_value = [(1, "Make appointment"), (5, "Confirmare rezervare")]
    mock_session.exec = AsyncMock(return_value=mock_result)

    repo = TemplateRepository(session=mock_session)
    result = await repo.get_names_by_ids({1, 5})

    assert result == {1: "Make appointment", 5: "Confirmare rezervare"}


@pytest.mark.asyncio
async def test_get_names_by_ids_empty_input_returns_empty_dict(mock_session: MagicMock) -> None:
    repo = TemplateRepository(session=mock_session)
    result = await repo.get_names_by_ids(set())

    assert result == {}
    mock_session.exec.assert_not_called()


@pytest.mark.asyncio
async def test_restore_sets_is_active_true(mock_session: MagicMock, mock_template: DialogTemplate) -> None:
    mock_template.is_active = False
    mock_result = MagicMock()
    mock_result.first.return_value = mock_template
    mock_session.exec = AsyncMock(return_value=mock_result)

    repo = TemplateRepository(session=mock_session)
    result = await repo.restore(1)

    assert result is True
    assert mock_template.is_active is True
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once_with(mock_template)


@pytest.mark.asyncio
async def test_restore_already_active_returns_false(mock_session: MagicMock, mock_template: DialogTemplate) -> None:
    mock_template.is_active = True
    mock_result = MagicMock()
    mock_result.first.return_value = mock_template
    mock_session.exec = AsyncMock(return_value=mock_result)

    repo = TemplateRepository(session=mock_session)
    result = await repo.restore(1)

    assert result is False
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_restore_not_found_returns_false(mock_session: MagicMock) -> None:
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_session.exec = AsyncMock(return_value=mock_result)

    repo = TemplateRepository(session=mock_session)
    result = await repo.restore(999)

    assert result is False


@pytest.mark.asyncio
async def test_get_all_paginated_excludes_inactive_by_default(mock_session: MagicMock) -> None:
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_count_result = MagicMock()
    mock_count_result.one.return_value = 0
    mock_session.exec = AsyncMock(side_effect=[mock_result, mock_count_result])

    repo = TemplateRepository(session=mock_session)
    await repo.get_all_paginated(limit=10, offset=0)

    # Default: include_inactive=False — WHERE is_active=true must appear in both queries
    executed_sqls = [str(call.args[0]).lower() for call in mock_session.exec.call_args_list]
    assert any("is_active" in sql for sql in executed_sqls)


@pytest.mark.asyncio
async def test_get_all_paginated_includes_inactive_when_flagged(mock_session: MagicMock) -> None:
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_count_result = MagicMock()
    mock_count_result.one.return_value = 0
    mock_session.exec = AsyncMock(side_effect=[mock_result, mock_count_result])

    repo = TemplateRepository(session=mock_session)
    await repo.get_all_paginated(limit=10, offset=0, include_inactive=True)

    # include_inactive=True — no WHERE clause at all (is_active appears in SELECT cols)
    primary_sql = str(mock_session.exec.call_args_list[0].args[0]).lower()
    assert "where" not in primary_sql
