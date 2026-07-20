import os

from locust import HttpUser, between, task


class EduFlowUser(HttpUser):
    """覆盖公开浏览和登录后读取接口的基础压测用户。"""

    host = os.getenv("LOCUST_HOST", "http://127.0.0.1:8000")
    wait_time = between(1, 3)

    def on_start(self) -> None:
        self.token: str | None = None
        account = os.getenv("LOCUST_ACCOUNT")
        password = os.getenv("LOCUST_PASSWORD")
        if not account or not password:
            return
        with self.client.post(
            "/api/v1/auth/login",
            json={"account": account, "password": password},
            name="POST /auth/login",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"登录失败：HTTP {response.status_code}")
                return
            payload = response.json()
            if payload.get("code") != 0:
                response.failure(f"登录失败：{payload.get('message')}")
                return
            self.token = payload["data"]["access_token"]

    @property
    def auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    @task(5)
    def browse_courses(self) -> None:
        self.client.get("/api/v1/courses?page=1&page_size=20", name="GET /courses")

    @task(2)
    def health_check(self) -> None:
        self.client.get("/health", name="GET /health")

    @task(3)
    def read_learning_data(self) -> None:
        if not self.token:
            return
        self.client.get(
            "/api/v1/learning/courses",
            headers=self.auth_headers,
            name="GET /learning/courses",
        )
        self.client.get(
            "/api/v1/notifications?page=1&page_size=20",
            headers=self.auth_headers,
            name="GET /notifications",
        )
