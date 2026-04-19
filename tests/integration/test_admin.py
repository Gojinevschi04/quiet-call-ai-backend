from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from app.modules.tasks.schema import AdminStatsResponse, TaskStatsResponse, TaskStatus
from app.modules.users.schema import UserRole

# --- Stats ---


@pytest.mark.asyncio
async def test_get_admin_stats(admin_client: AsyncClient) -> None:
    with patch("app.modules.admin.service.AdminService.get_system_stats") as mock_stats:
        mock_stats.return_value = AdminStatsResponse(
            total_users=10,
            total_tasks=50,
            tasks_by_status=TaskStatsResponse(
                total=50, pending=5, scheduled=3, in_progress=2, completed=35, failed=5
            ),
            total_calls=40,
        )
        response = await admin_client.get("/admin/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_users"] == 10
        assert data["total_tasks"] == 50
        assert data["total_calls"] == 40
        assert data["tasks_by_status"]["completed"] == 35


@pytest.mark.asyncio
async def test_get_admin_stats_non_admin(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.get("/admin/stats")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_admin_stats_unauthenticated(client: AsyncClient) -> None:
    response = await client.get("/admin/stats")
    assert response.status_code == 401


# --- Admin Users ---


@pytest.mark.asyncio
async def test_get_admin_users(admin_client: AsyncClient) -> None:
    with patch("app.modules.admin.service.AdminService.get_all_users") as mock_get:
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "user@test.com"
        mock_user.role = UserRole.USER
        mock_user.phone_number = "+37312345678"
        mock_user.created_at.isoformat.return_value = "2026-01-01T00:00:00"
        mock_user.updated_at.isoformat.return_value = "2026-01-01T00:00:00"
        mock_get.return_value = ([mock_user], 1)

        response = await admin_client.get("/admin/users")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["users"][0]["email"] == "user@test.com"


@pytest.mark.asyncio
async def test_get_admin_users_non_admin(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.get("/admin/users")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_admin_users_unauthenticated(client: AsyncClient) -> None:
    response = await client.get("/admin/users")
    assert response.status_code == 401


# --- Admin Tasks ---


@pytest.mark.asyncio
async def test_get_admin_tasks(admin_client: AsyncClient) -> None:
    with patch("app.modules.admin.service.AdminService.get_all_tasks") as mock_get:
        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.target_phone = "+37312345678"
        mock_task.status = TaskStatus.COMPLETED
        mock_task.template_id = 1
        mock_task.slot_data = {}
        mock_task.scheduled_time = None
        mock_task.summary = "Done"
        mock_task.error_reason = None
        mock_task.created_at = "2026-01-01T00:00:00"
        mock_task.updated_at = "2026-01-01T00:00:00"
        mock_get.return_value = ([mock_task], 1)

        response = await admin_client.get("/admin/tasks")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["target_phone"] == "+37312345678"


@pytest.mark.asyncio
async def test_get_admin_tasks_with_status_filter(admin_client: AsyncClient) -> None:
    with patch("app.modules.admin.service.AdminService.get_all_tasks") as mock_get:
        mock_get.return_value = ([], 0)
        response = await admin_client.get("/admin/tasks?status=failed")
        assert response.status_code == 200
        assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_get_admin_tasks_non_admin(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.get("/admin/tasks")
    assert response.status_code == 403


# --- Update User Role ---


@pytest.mark.asyncio
async def test_update_user_role(admin_client: AsyncClient) -> None:
    with patch("app.modules.admin.service.AdminService.update_user_role") as mock_update:
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "user@test.com"
        mock_user.role = UserRole.ADMIN
        mock_user.phone_number = None
        mock_user.created_at.isoformat.return_value = "2026-01-01T00:00:00"
        mock_user.updated_at.isoformat.return_value = "2026-01-01T00:00:00"
        mock_update.return_value = mock_user

        response = await admin_client.put("/admin/users/1", json={"role": "admin"})
        assert response.status_code == 200
        assert response.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_update_user_role_not_found(admin_client: AsyncClient) -> None:
    with patch("app.modules.admin.service.AdminService.update_user_role") as mock_update:
        mock_update.return_value = None
        response = await admin_client.put("/admin/users/999", json={"role": "admin"})
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_user_role_self_blocked(admin_client: AsyncClient) -> None:
    response = await admin_client.put("/admin/users/2", json={"role": "user"})  # admin has id=2
    assert response.status_code == 400
    assert "Cannot change your own role" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_user_role_no_role(admin_client: AsyncClient) -> None:
    response = await admin_client.put("/admin/users/1", json={})
    assert response.status_code == 400
    assert "Role is required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_user_role_non_admin(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.put("/admin/users/1", json={"role": "admin"})
    assert response.status_code == 403


# --- Delete User via Admin ---


@pytest.mark.asyncio
async def test_delete_admin_user(admin_client: AsyncClient) -> None:
    with patch("app.modules.admin.service.AdminService.delete_user") as mock_delete:
        mock_delete.return_value = True
        response = await admin_client.delete("/admin/users/1")
        assert response.status_code == 200
        assert response.json()["message"] == "User deleted successfully"


@pytest.mark.asyncio
async def test_delete_admin_user_not_found(admin_client: AsyncClient) -> None:
    with patch("app.modules.admin.service.AdminService.delete_user") as mock_delete:
        mock_delete.return_value = False
        response = await admin_client.delete("/admin/users/999")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_admin_user_self_blocked(admin_client: AsyncClient) -> None:
    response = await admin_client.delete("/admin/users/2")  # admin has id=2
    assert response.status_code == 400
    assert "Cannot delete your own account" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_admin_user_non_admin(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.delete("/admin/users/1")
    assert response.status_code == 403


# --- Password Reset ---


@pytest.mark.asyncio
async def test_password_reset(client: AsyncClient) -> None:
    with patch("app.modules.users.repository.UserRepository.get_by_email") as mock_get:
        mock_get.return_value = None
        response = await client.post("/auth/reset-password", json={"email": "test@example.com"})
        assert response.status_code == 200
        assert "reset link" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_password_reset_existing_email(client: AsyncClient) -> None:
    with patch("app.modules.users.repository.UserRepository.get_by_email") as mock_get:
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "existing@example.com"
        mock_get.return_value = mock_user
        response = await client.post("/auth/reset-password", json={"email": "existing@example.com"})
        assert response.status_code == 200
        assert "reset link" in response.json()["message"].lower()


# --- Access control on /users/ endpoints ---


@pytest.mark.asyncio
async def test_create_user_non_admin_forbidden(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.post(
        "/users/",
        json={"email": "new@example.com", "password": "test12345", "role": "user"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_users_non_admin_forbidden(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.get("/users/")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_user_non_admin_forbidden(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.delete("/users/1")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_self_deletion_prevented(admin_client: AsyncClient) -> None:
    response = await admin_client.delete("/users/2")
    assert response.status_code == 400
    assert "Cannot delete your own account" in response.json()["detail"]


# --- Validation edge cases ---


@pytest.mark.asyncio
async def test_update_user_role_invalid_value(admin_client: AsyncClient) -> None:
    response = await admin_client.put("/admin/users/1", json={"role": "superadmin"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_admin_users_invalid_limit(admin_client: AsyncClient) -> None:
    response = await admin_client.get("/admin/users?limit=0")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_admin_tasks_invalid_limit(admin_client: AsyncClient) -> None:
    response = await admin_client.get("/admin/tasks?limit=101")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_admin_tasks_unauthenticated(client: AsyncClient) -> None:
    response = await client.get("/admin/tasks")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_admin_user_unauthenticated(client: AsyncClient) -> None:
    response = await client.delete("/admin/users/1")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_user_role_unauthenticated(client: AsyncClient) -> None:
    response = await client.put("/admin/users/1", json={"role": "admin"})
    assert response.status_code == 401


# --- Pagination edge cases ---


@pytest.mark.asyncio
async def test_get_admin_users_negative_offset(admin_client: AsyncClient) -> None:
    response = await admin_client.get("/admin/users?offset=-1")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_admin_users_limit_too_high(admin_client: AsyncClient) -> None:
    response = await admin_client.get("/admin/users?limit=101")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_admin_tasks_negative_offset(admin_client: AsyncClient) -> None:
    response = await admin_client.get("/admin/tasks?offset=-1")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_admin_tasks_invalid_status(admin_client: AsyncClient) -> None:
    response = await admin_client.get("/admin/tasks?status=nonexistent")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_admin_tasks_with_pagination(admin_client: AsyncClient) -> None:
    with patch("app.modules.admin.service.AdminService.get_all_tasks") as mock_get:
        mock_get.return_value = ([], 0)
        response = await admin_client.get("/admin/tasks?limit=10&offset=20")
        assert response.status_code == 200
        mock_get.assert_called_once_with(10, 20, None)


@pytest.mark.asyncio
async def test_get_admin_users_with_pagination(admin_client: AsyncClient) -> None:
    with patch("app.modules.admin.service.AdminService.get_all_users") as mock_get:
        mock_get.return_value = ([], 0)
        response = await admin_client.get("/admin/users?limit=10&offset=5")
        assert response.status_code == 200
        mock_get.assert_called_once_with(10, 5)


@pytest.mark.asyncio
async def test_update_user_role_invalid_user_id_type(admin_client: AsyncClient) -> None:
    response = await admin_client.put("/admin/users/abc", json={"role": "admin"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_delete_admin_user_invalid_user_id_type(admin_client: AsyncClient) -> None:
    response = await admin_client.delete("/admin/users/abc")
    assert response.status_code == 422


# --- Cascade delete and self-role-change ---


@pytest.mark.asyncio
async def test_delete_user_with_tasks(admin_client: AsyncClient) -> None:
    with patch("app.modules.admin.service.AdminService.delete_user") as mock_delete:
        mock_delete.return_value = True
        response = await admin_client.delete("/admin/users/1")
        assert response.status_code == 200
        assert response.json()["message"] == "User deleted successfully"


@pytest.mark.asyncio
async def test_get_extended_stats_admin(admin_client: AsyncClient) -> None:
    with patch("app.modules.admin.service.AdminService.get_extended_stats") as mock_stats:
        mock_stats.return_value = {
            "tasks_per_template": [],
            "average_call_duration": 0,
            "tasks_per_day": [],
            "users_per_month": [],
            "success_rate_per_template": [],
        }
        response = await admin_client.get("/admin/stats/extended")
        assert response.status_code == 200
        data = response.json()
        assert "tasks_per_template" in data
        assert "success_rate_per_template" in data


@pytest.mark.asyncio
async def test_get_extended_stats_requires_admin(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.get("/admin/stats/extended")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_extended_stats_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/admin/stats/extended")
    assert response.status_code == 401
