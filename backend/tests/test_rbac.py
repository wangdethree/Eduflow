from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.rbac import Permission, Role
from app.models.user import User


async def create_admin_and_token(client):
    async with AsyncSessionLocal() as session:
        user = User(
            username="admin",
            email="admin@example.com",
            nickname="管理员",
            password_hash=hash_password("Admin1234"),
        )
        manage_roles = Permission(name="角色管理", code="role:manage")
        manage_users = Permission(name="用户管理", code="user:manage")
        role = Role(name="管理员", code="admin", is_system=True)
        role.permissions = [manage_roles, manage_users]
        user.roles = [role]
        session.add(user)
        await session.commit()
    response = await client.post(
        "/api/v1/auth/login", json={"account": "admin", "password": "Admin1234"}
    )
    return response.json()["data"]["access_token"]


async def test_ordinary_user_cannot_manage_roles(client):
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "student02",
            "email": "student02@example.com",
            "password": "Study1234",
        },
    )
    login = await client.post(
        "/api/v1/auth/login", json={"account": "student02", "password": "Study1234"}
    )
    token = login.json()["data"]["access_token"]
    response = await client.get("/api/v1/roles", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


async def test_role_permission_and_user_assignment_flow(client):
    token = await create_admin_and_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    permission = await client.post(
        "/api/v1/permissions",
        headers=headers,
        json={"name": "创建课程", "code": "course:create"},
    )
    role = await client.post(
        "/api/v1/roles",
        headers=headers,
        json={"name": "教师", "code": "teacher", "description": "课程教师"},
    )
    role_id = role.json()["data"]["id"]
    permission_id = permission.json()["data"]["id"]
    assigned = await client.put(
        f"/api/v1/roles/{role_id}/permissions", headers=headers, json={"ids": [permission_id]}
    )
    assert assigned.json()["data"]["permissions"][0]["code"] == "course:create"

    register = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "teacher01",
            "email": "teacher@example.com",
            "password": "Teach1234",
        },
    )
    user_id = register.json()["data"]["id"]
    user_result = await client.put(
        f"/api/v1/users/{user_id}/roles", headers=headers, json={"ids": [role_id]}
    )
    assert user_result.json()["data"]["roles"][0]["code"] == "teacher"

    logs = await client.get(
        "/api/v1/operation-logs", headers=headers, params={"action": "assign"}
    )
    assert logs.status_code == 200
    assert logs.json()["data"]["total"] == 2
    assert {item["action"] for item in logs.json()["data"]["items"]} == {
        "role:assign_permissions",
        "user:assign_roles",
    }

    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.id == user_id))
        assert user is not None and user.token_version == 2


async def test_cannot_disable_current_admin(client):
    token = await create_admin_and_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.patch(
        "/api/v1/users/1/status", headers=headers, json={"status": "disabled"}
    )
    assert response.status_code == 409
