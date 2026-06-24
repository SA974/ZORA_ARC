import pytest

from app.api import health as health_module


@pytest.mark.anyio
async def test_health_endpoint_shape(monkeypatch):
    class FakeDbHealth:
        def as_dict(self):
            return {"ok": False, "extensions": {}}

    class FakeHindsight:
        def __init__(self, settings):
            self.settings = settings

        async def health(self):
            return {"ok": False, "configured": False}

    monkeypatch.setattr(health_module, "check_database_health", lambda settings: FakeDbHealth())
    monkeypatch.setattr(health_module, "HindsightClient", FakeHindsight)
    body = await health_module.health()
    assert body["app"]["name"] == "ARC-MEM Bridge"
    assert "postgres" in body
    assert "hindsight" in body
