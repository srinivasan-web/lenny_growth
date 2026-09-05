from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_chat_service_factory, get_health_service, get_session_service, get_ship30_service_factory
from app.main import app
from app.models.schemas import DependencyStatus, HealthResponse, MessageResponse, SessionResponse
from app.rag.grounded import SourceCitation
from app.services.ship30 import Ship30Artifact


class FakeSessions:
    def __init__(self) -> None:
        self.session_id = uuid4()

    async def create(self, title: str | None) -> SessionResponse:
        now = datetime.now(timezone.utc)
        return SessionResponse(id=self.session_id, title=title, created_at=now, updated_at=now, messages=[])

    async def get(self, session_id):
        now = datetime.now(timezone.utc)
        message = MessageResponse(id=uuid4(), role="user", content="Hi", provider=None, model=None, source_metadata=None, created_at=now)
        return SessionResponse(id=session_id, title="Test", created_at=now, updated_at=now, messages=[message])


class FakeHealth:
    async def check(self) -> HealthResponse:
        ok = DependencyStatus(status="ok")
        return HealthResponse(status="ok", database=ok, ollama=ok, vector_index=ok)


class FakeChat:
    async def ensure_session(self, session_id) -> None:
        return None

    async def stream(self, session_id, content):
        yield "event: status\ndata: {\"status\": \"retrieving\"}\n\n"
        yield "event: done\ndata: {\"response\": {}}\n\n"


class FakeShip30:
    async def generate(self, topic: str) -> Ship30Artifact:
        return Ship30Artifact(
            markdown="# A useful essay",
            word_count=1250,
            sources=[SourceCitation(source_id="S1", episode="Episode", guest=None, timestamp=None, topic=None, source_url="https://example.com", similarity_score=0.9)],
            provider="stub",
            model="stub-model",
        )


def test_api_endpoints_use_service_contracts() -> None:
    sessions = FakeSessions()
    app.dependency_overrides[get_session_service] = lambda: sessions
    app.dependency_overrides[get_health_service] = lambda: FakeHealth()
    app.dependency_overrides[get_chat_service_factory] = lambda: (lambda provider=None: FakeChat())
    app.dependency_overrides[get_ship30_service_factory] = lambda: (lambda provider=None: FakeShip30())
    try:
        with TestClient(app) as client:
            created = client.post("/api/sessions", json={"title": "Research"})
            assert created.status_code == 201
            session_id = created.json()["id"]
            assert client.get(f"/api/sessions/{session_id}").status_code == 200
            chat = client.post("/api/chat", json={"session_id": session_id, "message": "Hello"})
            assert chat.status_code == 200
            assert "event: done" in chat.text
            content = client.post("/api/content/ship-30", json={"topic": "activation"})
            assert content.status_code == 200
            assert content.json()["word_count"] == 1250
            health = client.get("/api/health")
            assert health.status_code == 200
            assert health.json()["vector_index"]["status"] == "ok"
    finally:
        app.dependency_overrides.clear()
