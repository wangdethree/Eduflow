import asyncio

from app.core import observability


class FakeRedis:
    def __init__(self, queue_size: int = 0) -> None:
        self.queue_size = queue_size
        self.closed = False

    async def llen(self, _queue: str) -> int:
        return self.queue_size

    async def aclose(self) -> None:
        self.closed = True


def test_query_operation_is_low_cardinality():
    assert observability._query_operation("  select * from users") == "SELECT"
    assert observability._query_operation("") == "UNKNOWN"


async def test_collect_dependency_metrics(monkeypatch):
    clients = [FakeRedis(), FakeRedis(queue_size=7)]

    async def fake_probe(_url: str, dependency: str) -> FakeRedis:
        observability.DEPENDENCY_UP.labels(dependency=dependency).set(1)
        return clients.pop(0)

    monkeypatch.setattr(observability, "_probe_redis", fake_probe)

    await observability.collect_dependency_metrics()

    assert observability.DEPENDENCY_UP.labels(dependency="database")._value.get() == 1
    assert observability.DEPENDENCY_UP.labels(dependency="redis")._value.get() == 1
    assert observability.DEPENDENCY_UP.labels(dependency="celery_broker")._value.get() == 1
    assert observability.CELERY_QUEUE_MESSAGES._value.get() == 7


async def test_dependency_probe_task_can_be_stopped(monkeypatch):
    probe_finished = asyncio.Event()

    async def fake_collect() -> None:
        probe_finished.set()

    monkeypatch.setattr(observability, "collect_dependency_metrics", fake_collect)
    task = observability.start_dependency_probes()
    await asyncio.wait_for(probe_finished.wait(), timeout=1)

    await observability.stop_dependency_probes(task)

    assert task.cancelled()
