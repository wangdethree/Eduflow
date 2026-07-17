from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.rbac import Permission, Role
from app.models.user import User
from app.services import notification as notification_service


class FakeRedis:
    def __init__(self) -> None:
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, ex=None):
        self.values[key] = str(value)
        return True

    async def delete(self, key):
        self.values.pop(key, None)
        return 1


async def create_users() -> tuple[int, int]:
    async with AsyncSessionLocal() as session:
        manager = User(
            username="notice_admin",
            email="notice_admin@example.com",
            nickname="通知管理员",
            password_hash=hash_password("Manager123"),
        )
        receiver = User(
            username="notice_user",
            email="notice_user@example.com",
            nickname="接收者",
            password_hash=hash_password("Receiver123"),
        )
        permission = Permission(name="通知管理", code="notification:manage")
        manager.roles = [
            Role(name="通知管理员", code="notice_manager", permissions=[permission])
        ]
        session.add_all([manager, receiver])
        await session.commit()
        return manager.id, receiver.id


async def login(client, account: str, password: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"account": account, "password": password}
    )
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


async def test_notification_unread_and_read_flow(client, monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(notification_service, "get_redis_client", lambda: fake)
    _, receiver_id = await create_users()
    manager_headers = await login(client, "notice_admin", "Manager123")
    receiver_headers = await login(client, "notice_user", "Receiver123")
    created = await client.post(
        "/api/v1/notifications/broadcast",
        headers=manager_headers,
        json={
            "title": "系统维护通知",
            "content": "平台将于今晚进行维护。",
            "notification_type": "system",
            "user_ids": [receiver_id],
        },
    )
    assert created.status_code == 201
    unread = await client.get("/api/v1/notifications/unread-count", headers=receiver_headers)
    assert unread.json()["data"]["count"] == 1
    messages = await client.get("/api/v1/notifications", headers=receiver_headers)
    message_id = messages.json()["data"][0]["id"]
    marked = await client.post(
        f"/api/v1/notifications/{message_id}/read", headers=receiver_headers
    )
    assert marked.status_code == 200
    after = await client.get("/api/v1/notifications/unread-count", headers=receiver_headers)
    assert after.json()["data"]["count"] == 0
