from app.core.security import decode_token

USER = {
    "username": "student01",
    "email": "student@example.com",
    "password": "Study1234",
    "nickname": "小流",
}


async def register_and_login(client):
    register_response = await client.post("/api/v1/auth/register", json=USER)
    assert register_response.status_code == 201
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"account": USER["username"], "password": USER["password"]},
    )
    assert login_response.status_code == 200
    return login_response.json()["data"]


async def test_register_login_and_current_user(client):
    tokens = await register_and_login(client)
    assert decode_token(tokens["access_token"], "access")["sub"] == "1"
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["email"] == USER["email"]


async def test_duplicate_registration_and_wrong_password(client):
    await client.post("/api/v1/auth/register", json=USER)
    duplicate = await client.post("/api/v1/auth/register", json=USER)
    assert duplicate.status_code == 409
    wrong = await client.post(
        "/api/v1/auth/login", json={"account": USER["username"], "password": "wrong"}
    )
    assert wrong.status_code == 401
    assert wrong.json()["message"] == "账号或密码错误"


async def test_refresh_token_rotation_and_logout(client):
    tokens = await register_and_login(client)
    refreshed = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 200
    new_refresh = refreshed.json()["data"]["refresh_token"]
    reused = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert reused.status_code == 401
    logout = await client.post("/api/v1/auth/logout", json={"refresh_token": new_refresh})
    assert logout.status_code == 200
    after_logout = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": new_refresh}
    )
    assert after_logout.status_code == 401


async def test_update_profile_and_change_password_revokes_access(client):
    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    profile = await client.patch("/api/v1/auth/me", headers=headers, json={"nickname": "新昵称"})
    assert profile.json()["data"]["nickname"] == "新昵称"
    changed = await client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"old_password": USER["password"], "new_password": "NewStudy5678"},
    )
    assert changed.status_code == 200
    expired_access = await client.get("/api/v1/auth/me", headers=headers)
    assert expired_access.status_code == 401
    old_login = await client.post(
        "/api/v1/auth/login",
        json={"account": USER["username"], "password": USER["password"]},
    )
    assert old_login.status_code == 401
    new_login = await client.post(
        "/api/v1/auth/login", json={"account": USER["username"], "password": "NewStudy5678"}
    )
    assert new_login.status_code == 200


async def test_password_strength_validation(client):
    response = await client.post(
        "/api/v1/auth/register", json={**USER, "username": "weakuser", "password": "abcdefgh"}
    )
    assert response.status_code == 422
