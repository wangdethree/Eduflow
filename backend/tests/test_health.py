async def test_health_check(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"
    assert response.headers["X-Request-ID"].startswith("req_")


async def test_prometheus_metrics(client):
    response = await client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "eduflow_dependency_up" in response.text
    assert "eduflow_sql_query_duration_seconds" in response.text
