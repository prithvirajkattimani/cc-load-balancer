import pytest

from app.app import MemoryStore, create_app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("INSTANCE_NAME", "test-1")
    return create_app(MemoryStore()).test_client()


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok", "instance": "test-1"}


def test_whoami_returns_instance_info(client):
    data = client.get("/api/whoami").get_json()
    assert data["instance"] == "test-1"
    assert {"hostname", "instance_hits", "total_hits"} <= set(data)


def test_counter_increments_per_request(client):
    for _ in range(3):
        data = client.get("/api/whoami").get_json()
    assert data["instance_hits"] == 3
    assert data["total_hits"] == 3


def test_two_instances_share_one_store(monkeypatch):
    """Simulates two containers writing to the same Redis."""
    shared = MemoryStore()
    monkeypatch.setenv("INSTANCE_NAME", "app-1")
    c1 = create_app(shared).test_client()
    monkeypatch.setenv("INSTANCE_NAME", "app-2")
    c2 = create_app(shared).test_client()

    c1.get("/api/whoami")
    c2.get("/api/whoami")
    c2.get("/api/whoami")

    stats = c1.get("/api/stats").get_json()
    assert stats["hits"] == {"app-1": 1, "app-2": 2}
    assert stats["total"] == 3


def test_reset_clears_counters(client):
    client.get("/api/whoami")
    assert client.post("/api/reset").status_code == 200
    assert client.get("/api/stats").get_json()["total"] == 0


def test_dashboard_page_loads(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Load Balancer Demo" in r.data


def test_unknown_route_returns_json_404(client):
    r = client.get("/nope")
    assert r.status_code == 404
    assert r.get_json() == {"error": "not found"}


def test_whoami_includes_all_instance_hits(client):
    """Dashboard reads counters from /api/whoami so it needs no extra request."""
    data = client.get("/api/whoami").get_json()
    assert data["hits"] == {"test-1": 1}
