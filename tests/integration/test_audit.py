from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient


def _build_mock_entry(
    entry_id: int = 1,
    user_id: int | None = 2,
    action: str = "task.create",
    target_type: str = "task",
    target_id: int | None = 42,
    details: str | None = "Created",
) -> MagicMock:
    entry = MagicMock()
    entry.id = entry_id
    entry.user_id = user_id
    entry.action = action
    entry.target_type = target_type
    entry.target_id = target_id
    entry.details = details
    entry.created_at = datetime(2026, 4, 13, 12, 0, 0)
    return entry


# --- Admin access (happy paths) ---


@pytest.mark.asyncio
async def test_list_audit_log_as_admin(admin_client: AsyncClient) -> None:
    with patch("app.modules.audit.service.AuditService.list_entries") as mock_list:
        mock_list.return_value = ([_build_mock_entry()], 1)

        response = await admin_client.get("/admin/audit/")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["limit"] == 50
        assert data["offset"] == 0
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["id"] == 1
        assert item["user_id"] == 2
        assert item["action"] == "task.create"
        assert item["target_type"] == "task"
        assert item["target_id"] == 42
        assert item["details"] == "Created"


@pytest.mark.asyncio
async def test_list_audit_log_empty(admin_client: AsyncClient) -> None:
    with patch("app.modules.audit.service.AuditService.list_entries") as mock_list:
        mock_list.return_value = ([], 0)

        response = await admin_client.get("/admin/audit/")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_audit_log_supports_nullable_fields(admin_client: AsyncClient) -> None:
    with patch("app.modules.audit.service.AuditService.list_entries") as mock_list:
        entry = _build_mock_entry(
            entry_id=7, user_id=None, target_id=None, details=None
        )
        mock_list.return_value = ([entry], 1)

        response = await admin_client.get("/admin/audit/")

        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["user_id"] is None
        assert item["target_id"] is None
        assert item["details"] is None


# --- Pagination ---


@pytest.mark.asyncio
async def test_list_audit_log_forwards_pagination_params(admin_client: AsyncClient) -> None:
    with patch("app.modules.audit.service.AuditService.list_entries") as mock_list:
        mock_list.return_value = ([], 0)

        response = await admin_client.get("/admin/audit/?limit=10&offset=20")

        assert response.status_code == 200
        mock_list.assert_called_once_with(10, 20)
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 20


@pytest.mark.asyncio
async def test_list_audit_log_uses_default_pagination(admin_client: AsyncClient) -> None:
    with patch("app.modules.audit.service.AuditService.list_entries") as mock_list:
        mock_list.return_value = ([], 0)

        response = await admin_client.get("/admin/audit/")

        assert response.status_code == 200
        mock_list.assert_called_once_with(50, 0)


# --- Validation ---


@pytest.mark.asyncio
async def test_list_audit_log_limit_too_high(admin_client: AsyncClient) -> None:
    response = await admin_client.get("/admin/audit/?limit=201")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_audit_log_limit_too_low(admin_client: AsyncClient) -> None:
    response = await admin_client.get("/admin/audit/?limit=0")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_audit_log_negative_offset(admin_client: AsyncClient) -> None:
    response = await admin_client.get("/admin/audit/?offset=-1")
    assert response.status_code == 422


# --- Access control ---


@pytest.mark.asyncio
async def test_list_audit_log_non_admin_forbidden(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.get("/admin/audit/")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_audit_log_unauthenticated(client: AsyncClient) -> None:
    response = await client.get("/admin/audit/")
    assert response.status_code == 401
