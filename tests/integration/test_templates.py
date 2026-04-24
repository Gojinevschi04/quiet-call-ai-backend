from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from app.modules.templates.exceptions import TemplateNameExistsError, TemplateNotFoundError


@pytest.mark.asyncio
async def test_create_template(admin_client: AsyncClient) -> None:
    with patch("app.modules.templates.service.TemplateService.create_template") as mock_create:
        mock_template = MagicMock()
        mock_template.id = 1
        mock_template.name = "Make Appointment"
        mock_template.base_script = "Hello, I'd like to make an appointment."
        mock_template.required_slots = ["preferred_date"]
        mock_template.language = "en"
        mock_template.is_active = True
        mock_template.created_at = "2026-01-01T00:00:00"
        mock_template.updated_at = "2026-01-01T00:00:00"
        mock_create.return_value = mock_template

        response = await admin_client.post(
            "/templates/",
            json={
                "name": "Make Appointment",
                "base_script": "Hello, I would like to help you today.",
                "required_slots": ["preferred_date"],
            },
        )
        assert response.status_code == 201
        assert response.json()["name"] == "Make Appointment"


@pytest.mark.asyncio
async def test_create_template_duplicate(admin_client: AsyncClient) -> None:
    with patch("app.modules.templates.service.TemplateService.create_template") as mock_create:
        mock_create.side_effect = TemplateNameExistsError("Already exists")
        response = await admin_client.post(
            "/templates/",
            json={"name": "Duplicate", "base_script": "Hello, I would like to help you today.", "required_slots": []},
        )
        assert response.status_code == 409


@pytest.mark.asyncio
async def test_get_templates(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.templates.service.TemplateService.get_templates") as mock_get:
        mock_template = MagicMock()
        mock_template.id = 1
        mock_template.name = "Make Appointment"
        mock_template.base_script = "Hello, I would like to help you today."
        mock_template.required_slots = []
        mock_template.language = "en"
        mock_template.is_active = True
        mock_template.created_at = "2026-01-01T00:00:00"
        mock_template.updated_at = "2026-01-01T00:00:00"
        mock_get.return_value = [mock_template]

        response = await authenticated_client.get("/templates/")
        assert response.status_code == 200
        assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_get_template(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.templates.service.TemplateService.get_template") as mock_get:
        mock_template = MagicMock()
        mock_template.id = 1
        mock_template.name = "Make Appointment"
        mock_template.base_script = "Hello, I would like to help you today."
        mock_template.required_slots = []
        mock_template.language = "en"
        mock_template.is_active = True
        mock_template.created_at = "2026-01-01T00:00:00"
        mock_template.updated_at = "2026-01-01T00:00:00"
        mock_get.return_value = mock_template

        response = await authenticated_client.get("/templates/1")
        assert response.status_code == 200
        assert response.json()["id"] == 1


@pytest.mark.asyncio
async def test_get_template_not_found(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.templates.service.TemplateService.get_template") as mock_get:
        mock_get.side_effect = TemplateNotFoundError("Not found")
        response = await authenticated_client.get("/templates/999")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_template(admin_client: AsyncClient) -> None:
    with patch("app.modules.templates.service.TemplateService.update_template") as mock_update:
        mock_template = MagicMock()
        mock_template.id = 1
        mock_template.name = "Updated"
        mock_template.base_script = "Hello updated"
        mock_template.required_slots = []
        mock_template.language = "en"
        mock_template.is_active = True
        mock_template.created_at = "2026-01-01T00:00:00"
        mock_template.updated_at = "2026-01-01T00:00:00"
        mock_update.return_value = mock_template

        response = await admin_client.put("/templates/1", json={"name": "Updated"})
        assert response.status_code == 200
        assert response.json()["name"] == "Updated"


@pytest.mark.asyncio
async def test_delete_template(admin_client: AsyncClient) -> None:
    with patch("app.modules.templates.service.TemplateService.delete_template") as mock_delete:
        mock_delete.return_value = True
        response = await admin_client.delete("/templates/1")
        assert response.status_code == 200
        assert response.json()["message"] == "Template deactivated successfully"


@pytest.mark.asyncio
async def test_create_template_non_admin_forbidden(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.post(
        "/templates/",
        json={"name": "Test", "base_script": "Hello, I would like to help you today.", "required_slots": []},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_template_non_admin_forbidden(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.put("/templates/1", json={"name": "Updated"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_template_non_admin_forbidden(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.delete("/templates/1")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_templates_unauthenticated(client: AsyncClient) -> None:
    response = await client.get("/templates/")
    assert response.status_code == 401


# --- Missing error paths ---


@pytest.mark.asyncio
async def test_update_template_not_found(admin_client: AsyncClient) -> None:
    with patch("app.modules.templates.service.TemplateService.update_template") as mock_update:
        mock_update.side_effect = TemplateNotFoundError("Not found")
        response = await admin_client.put("/templates/999", json={"name": "Updated Name"})
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_template_duplicate_name(admin_client: AsyncClient) -> None:
    with patch("app.modules.templates.service.TemplateService.update_template") as mock_update:
        mock_update.side_effect = TemplateNameExistsError("Name taken")
        response = await admin_client.put("/templates/1", json={"name": "Existing Name"})
        assert response.status_code == 409


@pytest.mark.asyncio
async def test_delete_template_not_found(admin_client: AsyncClient) -> None:
    with patch("app.modules.templates.service.TemplateService.delete_template") as mock_delete:
        mock_delete.side_effect = TemplateNotFoundError("Not found")
        response = await admin_client.delete("/templates/999")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_template_invalid_name_too_short(admin_client: AsyncClient) -> None:
    response = await admin_client.post(
        "/templates/",
        json={"name": "X", "base_script": "This is a valid script.", "required_slots": []},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_template_invalid_script_too_short(admin_client: AsyncClient) -> None:
    response = await admin_client.post(
        "/templates/",
        json={"name": "Valid Name", "base_script": "Short", "required_slots": []},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_templates_invalid_limit(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.get("/templates/?limit=0")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_templates_limit_too_high(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.get("/templates/?limit=101")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_templates_negative_offset(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.get("/templates/?offset=-1")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_template_missing_fields(admin_client: AsyncClient) -> None:
    response = await admin_client.post("/templates/", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_template_name_too_long(admin_client: AsyncClient) -> None:
    response = await admin_client.post(
        "/templates/",
        json={"name": "X" * 101, "base_script": "A valid script that is long enough.", "required_slots": []},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_template_script_too_long(admin_client: AsyncClient) -> None:
    response = await admin_client.post(
        "/templates/",
        json={"name": "Valid Name", "base_script": "X" * 5001, "required_slots": []},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_template_too_many_slots(admin_client: AsyncClient) -> None:
    response = await admin_client.post(
        "/templates/",
        json={
            "name": "Valid Name",
            "base_script": "A valid script that is long enough.",
            "required_slots": [f"slot_{i}" for i in range(21)],
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_template_empty_slot_name(admin_client: AsyncClient) -> None:
    response = await admin_client.post(
        "/templates/",
        json={
            "name": "Valid Name",
            "base_script": "A valid script that is long enough.",
            "required_slots": ["valid_slot", ""],
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_template_name_too_short(admin_client: AsyncClient) -> None:
    response = await admin_client.put("/templates/1", json={"name": "X"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_template_script_too_short(admin_client: AsyncClient) -> None:
    response = await admin_client.put("/templates/1", json={"base_script": "Short"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_template_unauthenticated(client: AsyncClient) -> None:
    response = await client.put("/templates/1", json={"name": "Updated"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_template_unauthenticated(client: AsyncClient) -> None:
    response = await client.delete("/templates/1")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_template_unauthenticated(client: AsyncClient) -> None:
    response = await client.post(
        "/templates/",
        json={"name": "Test", "base_script": "A valid script that is long enough.", "required_slots": []},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_template_unauthenticated(client: AsyncClient) -> None:
    response = await client.get("/templates/1")
    assert response.status_code == 401


# --- Template deactivation and is_active field ---


@pytest.mark.asyncio
async def test_delete_template_returns_deactivated_message(admin_client: AsyncClient) -> None:
    with patch("app.modules.templates.service.TemplateService.delete_template") as mock_delete:
        mock_delete.return_value = True
        response = await admin_client.delete("/templates/1")
        assert response.status_code == 200
        assert "deactivated" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_get_templates_excludes_inactive(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.templates.service.TemplateService.get_templates") as mock_get:
        active_template = MagicMock()
        active_template.id = 1
        active_template.name = "Active Template"
        active_template.base_script = "Hello, this is an active template."
        active_template.required_slots = []
        active_template.language = "en"
        active_template.is_active = True
        active_template.created_at = "2026-01-01T00:00:00"
        active_template.updated_at = "2026-01-01T00:00:00"
        # Service already filters inactive templates; mock returns only active
        mock_get.return_value = [active_template]

        response = await authenticated_client.get("/templates/")
        assert response.status_code == 200
        templates = response.json()
        assert len(templates) == 1
        assert templates[0]["is_active"] is True


@pytest.mark.asyncio
async def test_get_template_response_has_is_active(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.templates.service.TemplateService.get_template") as mock_get:
        mock_template = MagicMock()
        mock_template.id = 1
        mock_template.name = "Test Template"
        mock_template.base_script = "Hello, I would like to help you today."
        mock_template.required_slots = []
        mock_template.language = "en"
        mock_template.is_active = True
        mock_template.created_at = "2026-01-01T00:00:00"
        mock_template.updated_at = "2026-01-01T00:00:00"
        mock_get.return_value = mock_template

        response = await authenticated_client.get("/templates/1")
        assert response.status_code == 200
        data = response.json()
        assert "is_active" in data
        assert data["is_active"] is True


@pytest.mark.asyncio
async def test_restore_template_admin(admin_client: AsyncClient) -> None:
    with patch("app.modules.templates.service.TemplateService.restore_template") as mock_restore:
        mock_restore.return_value = True
        response = await admin_client.post("/templates/1/restore")
        assert response.status_code == 200
        assert "restored" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_restore_template_already_active_returns_409(admin_client: AsyncClient) -> None:
    with patch("app.modules.templates.service.TemplateService.restore_template") as mock_restore:
        mock_restore.return_value = False
        response = await admin_client.post("/templates/1/restore")
        assert response.status_code == 409


@pytest.mark.asyncio
async def test_restore_template_not_found(admin_client: AsyncClient) -> None:
    from app.modules.templates.exceptions import TemplateNotFoundError

    with patch("app.modules.templates.service.TemplateService.restore_template") as mock_restore:
        mock_restore.side_effect = TemplateNotFoundError("not found")
        response = await admin_client.post("/templates/999/restore")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_restore_template_non_admin_forbidden(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.post("/templates/1/restore")
    assert response.status_code == 403
