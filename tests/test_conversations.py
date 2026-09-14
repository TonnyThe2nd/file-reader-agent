import json
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app.core.config import settings
from app.main import app
from app.models import Conversation, Interaction


@pytest.fixture
def provider(client, monkeypatch):
    calls = []
    monkeypatch.setattr(settings, "chat_model", "qwen-test")

    def handler(request):
        calls.append(json.loads(request.content))
        if request.url.path.endswith("/embeddings"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"index": i, "embedding": [1.0] + [0.0] * 767}
                        for i, _ in enumerate(calls[-1]["input"])
                    ]
                },
            )
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "O prazo e cinco dias."}}]}
        )

    monkeypatch.setattr(app.state.http_client, "_transport", httpx.MockTransport(handler))
    monkeypatch.setattr(app.state.http_client, "_mounts", {})
    return calls


def start(client, mode="direct"):
    response = client.post(
        "/ask",
        data={"question": "Qual o prazo?", "chat": "true", "mode": mode},
        files={"file": ("prazo.txt", b"O prazo e cinco dias.")},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_memory_resume_and_cache_context(client, provider):
    first = start(client)
    cid = first["conversation_id"]
    assert cid
    second = client.post(
        "/ask", data={"question": "Explique melhor esse prazo.", "conversation_id": cid}
    )
    assert second.status_code == 200, second.text
    contents = provider[-1]["messages"][1:]
    assert [m["role"] for m in contents] == ["user", "assistant", "user"]
    assert contents[0]["content"] == "Qual o prazo?"
    assert contents[1]["content"] == "O prazo e cinco dias."
    assert not second.json()["cache_hit"]
    detail = client.get("/conversations/" + cid).json()
    assert [m["turn_number"] for m in detail["messages"]] == [1, 2]
    assert client.get("/conversations").json()[0]["id"] == cid
    assert client.get("/interactions/" + first["interaction_id"]).json()["conversation_id"] == cid
    fresh = start(client)
    assert fresh["conversation_id"] != cid
    assert fresh["cache_hit"]  # same document and empty context


def test_source_content_and_rag_followup(client, provider):
    first = start(client, "rag")
    source = first["sources"][0]
    assert source["document_id"] == first["document_id"]
    content = client.get("/documents/" + first["document_id"] + "/content")
    assert content.content == b"O prazo e cinco dias."
    assert content.headers["cache-control"] == "no-store"
    assert content.headers["content-type"].startswith("text/plain")
    response = client.post(
        "/ask",
        data={
            "question": "E quando termina?",
            "conversation_id": first["conversation_id"],
            "mode": "rag",
        },
    )
    assert response.status_code == 200
    assert "Qual o prazo?" in provider[-2]["input"][0]


def test_conversation_owner_and_deleted_document(client, provider, monkeypatch):
    first = start(client)
    cid, did = first["conversation_id"], first["document_id"]
    monkeypatch.setattr(settings, "api_tokens", {"other": SecretStr("other-token")})
    client.headers["Authorization"] = "Bearer other-token"
    assert client.get("/conversations/" + cid).status_code == 404
    assert client.get("/documents/" + did + "/content").status_code == 404
    assert client.get("/documents/" + did).status_code == 404
    assert client.post("/ask", data={"question": "x", "conversation_id": cid}).status_code == 404
    assert client.get("/conversations").json() == []
    monkeypatch.setattr(settings, "api_tokens", {})
    assert (
        client.post(
            "/ask", data={"question": "x", "conversation_id": cid, "document_id": did}
        ).status_code
        == 422
    )
    assert client.delete("/documents/" + did).status_code == 204
    assert len(client.get("/conversations/" + cid).json()["messages"]) == 1
    assert client.post("/ask", data={"question": "x", "conversation_id": cid}).status_code == 410


def test_memory_bounded_and_message_pagination(client, provider, database):
    first = start(client)
    cid = UUID(first["conversation_id"])
    with database() as db:
        for i in range(2, 55):
            db.add(
                Interaction(
                    owner_id="local",
                    conversation_id=cid,
                    document_id=UUID(first["document_id"]),
                    turn_number=i,
                    question=f"Pergunta {i}",
                    answer="Resposta",
                    sources=[],
                    latency_ms=1,
                    model_used="test",
                    cache_hit=False,
                )
            )
        db.get(Conversation, cid).version = 54
        db.commit()
    page = client.get("/conversations/" + str(cid)).json()
    assert len(page["messages"]) == 50 and page["next_before"] == 5
    assert len(client.get("/conversations/" + str(cid) + "?before=5").json()["messages"]) == 4
    response = client.post("/ask", data={"question": "continue", "conversation_id": str(cid)})
    assert response.status_code == 200
    assert len(provider[-1]["messages"][1:]) == 13
    assert "Pergunta 49" == provider[-1]["messages"][1:][0]["content"]


def test_failed_turn_does_not_advance_conversation(client, provider, database, monkeypatch):
    first = start(client)
    monkeypatch.setattr(
        app.state.http_client, "_transport", httpx.MockTransport(lambda _: httpx.Response(503))
    )
    assert (
        client.post(
            "/ask", data={"question": "continue", "conversation_id": first["conversation_id"]}
        ).status_code
        == 503
    )
    with database() as db:
        assert db.get(Conversation, UUID(first["conversation_id"])).version == 1
        assert len(list(db.scalars(select(Interaction)))) == 1


def test_concurrent_turn_is_rejected(client, provider, database, monkeypatch):
    first = start(client)
    cid = UUID(first["conversation_id"])

    def handler(_):
        with database() as db:
            db.get(Conversation, cid).version += 1
            db.commit()
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "resposta desatualizada"}}]}
        )

    monkeypatch.setattr(app.state.http_client, "_transport", httpx.MockTransport(handler))
    response = client.post("/ask", data={"question": "continuar", "conversation_id": str(cid)})
    assert response.status_code == 409
    assert len(client.get("/conversations/" + str(cid)).json()["messages"]) == 1
