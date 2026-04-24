from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.templates.exceptions import TemplateNameExistsError, TemplateNotFoundError
from app.modules.templates.models import DialogTemplate
from app.modules.templates.repository import TemplateRepository
from app.modules.templates.schema import TemplateCreate, TemplateUpdate
from app.modules.templates.service import TemplateService


@pytest.mark.asyncio
async def test_create_template_success(mock_template: DialogTemplate) -> None:
    mock_repo = MagicMock(spec=TemplateRepository)
    mock_repo.get_by_name = AsyncMock(return_value=None)
    mock_repo.create = AsyncMock(return_value=mock_template)

    service = TemplateService(template_repository=mock_repo)
    data = TemplateCreate(
        name="Make Appointment",
        base_script="Hello, I'd like to help you today.",
        required_slots=["date"],
    )
    result = await service.create_template(data)

    assert result == mock_template
    mock_repo.create.assert_called_once()


@pytest.mark.asyncio
async def test_create_template_duplicate_name(mock_template: DialogTemplate) -> None:
    mock_repo = MagicMock(spec=TemplateRepository)
    mock_repo.get_by_name = AsyncMock(return_value=mock_template)

    service = TemplateService(template_repository=mock_repo)
    data = TemplateCreate(name="Make Appointment", base_script="Hello, I'd like to help you today.", required_slots=[])

    with pytest.raises(TemplateNameExistsError):
        await service.create_template(data)


@pytest.mark.asyncio
async def test_get_template_success(mock_template: DialogTemplate) -> None:
    mock_repo = MagicMock(spec=TemplateRepository)
    mock_repo.get_by_id = AsyncMock(return_value=mock_template)

    service = TemplateService(template_repository=mock_repo)
    result = await service.get_template(1)

    assert result == mock_template


@pytest.mark.asyncio
async def test_get_template_not_found() -> None:
    mock_repo = MagicMock(spec=TemplateRepository)
    mock_repo.get_by_id = AsyncMock(return_value=None)

    service = TemplateService(template_repository=mock_repo)

    with pytest.raises(TemplateNotFoundError):
        await service.get_template(999)


@pytest.mark.asyncio
async def test_get_templates(mock_template: DialogTemplate) -> None:
    mock_repo = MagicMock(spec=TemplateRepository)
    mock_repo.get_all_paginated = AsyncMock(return_value=([mock_template], 1))

    service = TemplateService(template_repository=mock_repo)
    result = await service.get_templates()

    assert len(result) == 1
    mock_repo.get_all_paginated.assert_called_once_with(50, 0, include_inactive=False)


@pytest.mark.asyncio
async def test_get_templates_with_pagination(mock_template: DialogTemplate) -> None:
    mock_repo = MagicMock(spec=TemplateRepository)
    mock_repo.get_all_paginated = AsyncMock(return_value=([mock_template], 1))

    service = TemplateService(template_repository=mock_repo)
    result = await service.get_templates(limit=10, offset=5)

    assert len(result) == 1
    mock_repo.get_all_paginated.assert_called_once_with(10, 5, include_inactive=False)


@pytest.mark.asyncio
async def test_update_template_success(mock_template: DialogTemplate) -> None:
    mock_repo = MagicMock(spec=TemplateRepository)
    mock_repo.get_by_id = AsyncMock(return_value=mock_template)
    mock_repo.get_by_name = AsyncMock(return_value=None)
    mock_repo.update = AsyncMock(return_value=mock_template)

    service = TemplateService(template_repository=mock_repo)
    data = TemplateUpdate(name="Updated Name")
    result = await service.update_template(1, data)

    assert result == mock_template


@pytest.mark.asyncio
async def test_update_template_not_found() -> None:
    mock_repo = MagicMock(spec=TemplateRepository)
    mock_repo.get_by_id = AsyncMock(return_value=None)

    service = TemplateService(template_repository=mock_repo)
    data = TemplateUpdate(name="Updated")

    with pytest.raises(TemplateNotFoundError):
        await service.update_template(999, data)


@pytest.mark.asyncio
async def test_delete_template_success(mock_template: DialogTemplate) -> None:
    mock_repo = MagicMock(spec=TemplateRepository)
    mock_repo.get_by_id = AsyncMock(return_value=mock_template)
    mock_repo.deactivate = AsyncMock(return_value=True)

    service = TemplateService(template_repository=mock_repo)
    result = await service.delete_template(1)

    assert result is True
    mock_repo.deactivate.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_delete_template_not_found() -> None:
    mock_repo = MagicMock(spec=TemplateRepository)
    mock_repo.get_by_id = AsyncMock(return_value=None)

    service = TemplateService(template_repository=mock_repo)

    with pytest.raises(TemplateNotFoundError):
        await service.delete_template(999)


@pytest.mark.asyncio
async def test_delete_template_already_inactive(mock_template: DialogTemplate) -> None:
    mock_template.is_active = False
    mock_repo = MagicMock(spec=TemplateRepository)
    mock_repo.get_by_id = AsyncMock(return_value=mock_template)

    service = TemplateService(template_repository=mock_repo)

    with pytest.raises(TemplateNotFoundError):
        await service.delete_template(1)


@pytest.mark.asyncio
async def test_update_template_only_base_script(mock_template: DialogTemplate) -> None:
    mock_repo = MagicMock(spec=TemplateRepository)
    mock_repo.get_by_id = AsyncMock(return_value=mock_template)
    mock_repo.update = AsyncMock(return_value=mock_template)

    service = TemplateService(template_repository=mock_repo)
    data = TemplateUpdate(base_script="Updated script content")
    result = await service.update_template(1, data)

    assert result == mock_template
    assert mock_template.base_script == "Updated script content"
    mock_repo.get_by_name.assert_not_called()


@pytest.mark.asyncio
async def test_update_template_only_slots(mock_template: DialogTemplate) -> None:
    mock_repo = MagicMock(spec=TemplateRepository)
    mock_repo.get_by_id = AsyncMock(return_value=mock_template)
    mock_repo.update = AsyncMock(return_value=mock_template)

    service = TemplateService(template_repository=mock_repo)
    data = TemplateUpdate(required_slots=["new_slot"])
    result = await service.update_template(1, data)

    assert result == mock_template
    assert mock_template.required_slots == ["new_slot"]


@pytest.mark.asyncio
async def test_update_template_duplicate_name(mock_template: DialogTemplate) -> None:
    existing_other = MagicMock(spec=DialogTemplate)
    existing_other.id = 2

    mock_repo = MagicMock(spec=TemplateRepository)
    mock_repo.get_by_id = AsyncMock(return_value=mock_template)
    mock_repo.get_by_name = AsyncMock(return_value=existing_other)

    service = TemplateService(template_repository=mock_repo)
    data = TemplateUpdate(name="Taken Name")

    with pytest.raises(TemplateNameExistsError):
        await service.update_template(1, data)


@pytest.mark.asyncio
async def test_restore_template_success(mock_template: DialogTemplate) -> None:
    """Soft-deleted template can be re-activated via restore_template."""
    mock_template.is_active = False
    mock_repo = MagicMock(spec=TemplateRepository)
    mock_repo.get_by_id = AsyncMock(return_value=mock_template)
    mock_repo.restore = AsyncMock(return_value=True)

    service = TemplateService(template_repository=mock_repo)
    result = await service.restore_template(1)

    assert result is True
    mock_repo.restore.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_restore_template_not_found_raises() -> None:
    mock_repo = MagicMock(spec=TemplateRepository)
    mock_repo.get_by_id = AsyncMock(return_value=None)

    service = TemplateService(template_repository=mock_repo)
    with pytest.raises(TemplateNotFoundError):
        await service.restore_template(999)


@pytest.mark.asyncio
async def test_restore_template_already_active_returns_false(mock_template: DialogTemplate) -> None:
    mock_template.is_active = True
    mock_repo = MagicMock(spec=TemplateRepository)
    mock_repo.get_by_id = AsyncMock(return_value=mock_template)

    service = TemplateService(template_repository=mock_repo)
    result = await service.restore_template(1)

    assert result is False
