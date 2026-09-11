import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app.core.config import settings
from app.main import app
from app.models import Document, DocumentChunk, Interaction
from app.services.document_service import cosine, split_document


@pytest.fixture
def provider(client, monkeypatch):
    calls = []
    monkeypatch.setattr(settings, "gemini_api_key", SecretStr("fake-key"))

    def handler(request):
        calls.append(request)
        if request.url.path.endswith(":batchEmbedContents"):
            requests = json.loads(request.content)["requests"]
            return httpx.Response(
                200, json={"embeddings": [{"values": [1.0] + [0.0] * 767} for _ in requests]}
            )
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "Resposta completa " * 30}]}}],
                "usageMetadata": {"promptTokenCount": 40, "candidatesTokenCount": 12},
                "modelVersion": "test-model",
            },
        )

    monkeypatch.setattr(app.state.http_client, "_transport", httpx.MockTransport(handler))
    monkeypatch.setattr(app.state.http_client, "_mounts", {})
    return calls


def ask(client, **data):
    return client.post(
        "/ask",
        data={"question": "Qual o total?", **data},
        files={"file": ("relatorio.txt", b"O total e 42.")},
    )


def test_complete_flow_cache_and_deletion(client, database, provider):
    first = ask(client)
    assert first.status_code == 200, first.text
    result = first.json()
    assert result["created_at"] and result["document_id"] and not result["cache_hit"]
    assert result["input_tokens"] == 40
    history = client.get("/interactions").json()
    assert history[0]["id"] == result["interaction_id"]
    assert len(history[0]["answer"]) == 200
    detail = client.get(f"/interactions/{result['interaction_id']}").json()
    assert detail["answer"] == result["answer"]
    assert (
        client.post(
            "/feedback",
            json={"interaction_id": result["interaction_id"], "rating": 1, "comment": "Util"},
        ).status_code
        == 200
    )
    assert client.get("/interactions").json()[0]["rating"] == 1
    assert client.get("/stats").json()["positive_rate"] == 100
    second = ask(client).json()
    assert second["cache_hit"] and second["interaction_id"] != result["interaction_id"]
    assert second["input_tokens"] == 0 and len(provider) == 1
    assert len(client.get("/documents").json()) == 1
    assert client.get("/stats").json()["total_interactions"] == 2
    assert client.delete(f"/documents/{result['document_id']}").status_code == 204
    assert client.get(f"/interactions/{result['interaction_id']}").json()["document_id"] is None
    assert client.delete(f"/interactions/{result['interaction_id']}").status_code == 204
    assert client.get("/stats").json()["total_feedbacks"] == 0


def test_rag_reuses_index_and_document(client, database, provider):
    result = ask(client, mode="rag").json()
    assert result["sources"][0]["content"] == "O total e 42."
    assert result["sources"][0]["section"] == "Texto, trecho 1"
    assert len(provider) == 3
    assert b"[1]" in provider[-1].content
    response = client.post(
        "/ask",
        data={"question": "Explique o total", "document_id": result["document_id"], "mode": "rag"},
    )
    assert response.status_code == 200, response.text
    assert len(provider) == 5  # only query embedding and generation
    with database() as db:
        assert len(list(db.scalars(select(DocumentChunk)))) == 1
    assert client.delete("/documents/" + result["document_id"]).status_code == 204
    with database() as db:
        assert not list(db.scalars(select(DocumentChunk)))


def test_cache_expiration_and_bypass(client, database, provider):
    first = ask(client).json()
    with database() as db:
        row = db.get(Interaction, UUID(first["interaction_id"]))
        row.created_at = datetime.now(timezone.utc) - timedelta(days=2)
        db.commit()
    assert not ask(client).json()["cache_hit"]
    assert not ask(client, use_cache="false").json()["cache_hit"]
    assert len(provider) == 3


def test_user_isolation_and_authentication(client, provider, monkeypatch):
    monkeypatch.setattr(
        settings, "api_tokens", {"alice": SecretStr("alice-secret"), "bob": SecretStr("bob-secret")}
    )
    assert client.get("/interactions").status_code == 401
    client.headers["Authorization"] = "Bearer alice-secret"
    first = ask(client).json()
    client.headers["Authorization"] = "Bearer bob-secret"
    assert client.get("/interactions").json() == []
    assert client.get("/documents").json() == []
    assert client.get("/stats").json()["total_interactions"] == 0
    assert client.get("/interactions/" + first["interaction_id"]).status_code == 404
    assert client.delete("/interactions/" + first["interaction_id"]).status_code == 404
    assert client.delete("/documents/" + first["document_id"]).status_code == 404
    assert (
        client.post(
            "/feedback", json={"interaction_id": first["interaction_id"], "rating": 1}
        ).status_code
        == 404
    )
    assert (
        client.post("/ask", data={"question": "x", "document_id": first["document_id"]}).status_code
        == 404
    )
    assert not ask(client).json()["cache_hit"]
    assert len(provider) == 2


def test_rate_limit_and_production_fail_closed(client, provider, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_per_minute", 1)
    assert ask(client).status_code == 200
    response = ask(client)
    assert response.status_code == 429 and response.headers["retry-after"] == "60"
    monkeypatch.setattr(settings, "app_env", "production")
    assert client.get("/interactions").status_code == 503
    assert client.get("/config").json()["auth_required"] is True


def test_upload_validation_search_and_ready(client, provider):
    assert client.get("/ready").status_code == 200
    document = client.post("/documents", files={"file": ("a.txt", b"content")}).json()
    assert (
        client.post(
            "/ask",
            data={"question": "x", "document_id": document["id"]},
            files={"file": ("a.txt", b"content")},
        ).status_code
        == 422
    )
    assert (
        client.post("/ask", data={"question": "x", "document_id": str(uuid4())}).status_code == 404
    )
    assert ask(client, mode="invalid").status_code == 422
    assert client.get("/interactions/not-a-uuid").status_code == 422
    ask(client)
    assert len(client.get("/interactions?search=total").json()) == 1
    assert client.get("/interactions?search=missing").json() == []
    assert client.get("/interactions?search=%25").json() == []


def test_failed_generation_not_saved(client, provider, database, monkeypatch):
    monkeypatch.setattr(
        app.state.http_client, "_transport", httpx.MockTransport(lambda _: httpx.Response(503))
    )
    assert ask(client).status_code == 503
    assert client.get("/interactions").json() == []
    with database() as db:
        assert len(list(db.scalars(select(Document)))) == 1  # upload survives a retry


def test_invalid_embeddings_fail_cleanly(client, provider, monkeypatch):
    monkeypatch.setattr(
        app.state.http_client,
        "_transport",
        httpx.MockTransport(lambda _: httpx.Response(200, json={"embeddings": [{"values": [1]}]})),
    )
    assert ask(client, mode="rag").status_code == 502
    assert client.get("/interactions").json() == []


def test_chunk_overlap_and_cosine():
    chunks = split_document(("a" * 4000).encode(), "text/plain")
    assert len(chunks) == 3 and len(chunks[0][1]) == 2000
    assert cosine([1, 0], [1, 0]) == 1
    assert cosine([1, 0], [0, 1]) == 0
    with pytest.raises(ValueError):
        cosine([1], [1, 0])
