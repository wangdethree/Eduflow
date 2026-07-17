from types import SimpleNamespace

from app.services import file as file_service

USER = {
    "username": "uploader",
    "email": "uploader@example.com",
    "password": "Upload1234",
}


class FakeMinio:
    def __init__(self) -> None:
        self.objects = set()

    def presigned_put_object(self, bucket, object_name, expires):
        self.objects.add((bucket, object_name))
        return f"http://minio.local/{bucket}/{object_name}?upload=1"

    def stat_object(self, bucket, object_name):
        assert (bucket, object_name) in self.objects
        return SimpleNamespace(size=1024, content_type="image/png")

    def presigned_get_object(self, bucket, object_name, expires):
        return f"http://minio.local/{bucket}/{object_name}?download=1"

    def remove_object(self, bucket, object_name):
        self.objects.discard((bucket, object_name))


async def authenticated_headers(client):
    await client.post("/api/v1/auth/register", json=USER)
    login = await client.post(
        "/api/v1/auth/login",
        json={"account": USER["username"], "password": USER["password"]},
    )
    return {"Authorization": f"Bearer {login.json()['data']['access_token']}"}


async def test_presigned_upload_complete_download_and_delete(client, monkeypatch):
    fake = FakeMinio()
    monkeypatch.setattr(file_service, "get_minio_client", lambda: fake)
    headers = await authenticated_headers(client)
    created = await client.post(
        "/api/v1/files/presigned-upload",
        headers=headers,
        json={
            "filename": "avatar.png",
            "content_type": "image/png",
            "size_bytes": 1024,
            "purpose": "avatar",
        },
    )
    assert created.status_code == 201
    file_id = created.json()["data"]["id"]
    assert "upload=1" in created.json()["data"]["url"]
    completed = await client.post(f"/api/v1/files/{file_id}/complete", headers=headers)
    assert completed.json()["data"]["status"] == "ready"
    download = await client.get(f"/api/v1/files/{file_id}/download", headers=headers)
    assert "download=1" in download.json()["data"]["url"]
    deleted = await client.delete(f"/api/v1/files/{file_id}", headers=headers)
    assert deleted.status_code == 200


async def test_reject_invalid_content_type(client, monkeypatch):
    monkeypatch.setattr(file_service, "get_minio_client", FakeMinio)
    headers = await authenticated_headers(client)
    response = await client.post(
        "/api/v1/files/presigned-upload",
        headers=headers,
        json={
            "filename": "attack.exe",
            "content_type": "application/octet-stream",
            "size_bytes": 1024,
            "purpose": "course_resource",
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == 70006
