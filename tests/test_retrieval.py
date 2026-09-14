import json

from pydantic import SecretStr

from app.core.config import settings
from app.services.retrieval_service import bm25
from tests.test_features import provider as provider_fixture

provider = provider_fixture


def upload(client, name, text):
    return client.post("/documents", files={"file": (name, text.encode())}).json()["id"]


def test_multi_document_context_and_cache(client, provider):
    a = upload(client, "a.txt", "Receita anual: 42 reais.")
    b = upload(client, "b.txt", "Despesa anual: 10 reais.")
    data = {"question": "Compare receita e despesa anual", "mode": "rag", "document_ids": [a, b]}
    first = client.post("/ask", data=data)
    assert first.status_code == 200, first.text
    assert {s["document_id"] for s in first.json()["sources"]} == {a, b}
    assert set(first.json()["document_ids"]) == {a, b}
    assert b"Receita anual" in provider[-1].content and b"Despesa anual" in provider[-1].content
    assert client.post("/ask", data={**data, "document_ids": [b, a]}).json()["cache_hit"]
    assert not client.post("/ask", data={**data, "document_ids": [a]}).json()["cache_hit"]
    assert not client.post("/ask", data={**data, "hybrid": "false"}).json()["cache_hit"]


def test_authorize_all_documents_before_provider(client, provider, monkeypatch):
    monkeypatch.setattr(settings, "api_tokens", {"a": SecretStr("a-key"), "b": SecretStr("b-key")})
    client.headers["Authorization"] = "Bearer a-key"
    a = upload(client, "a.txt", "Segredo Alice")
    client.headers["Authorization"] = "Bearer b-key"
    b = upload(client, "b.txt", "Segredo Bob")
    response = client.post(
        "/ask", data={"question": "segredos", "mode": "rag", "document_ids": [a, b]}
    )
    assert response.status_code == 404
    assert not provider


def test_conversation_retains_scope_and_rechecks_deletion(client, provider):
    a = upload(client, "a.txt", "Receita 42")
    b = upload(client, "b.txt", "Despesa 10")
    first = client.post(
        "/ask", data={"question": "Compare", "mode": "rag", "document_ids": [a, b], "chat": "true"}
    ).json()
    data = {"question": "Explique", "mode": "rag", "conversation_id": first["conversation_id"]}
    second = client.post("/ask", data=data)
    assert second.status_code == 200, second.text
    assert set(second.json()["document_ids"]) == {a, b}
    client.delete("/documents/" + b)
    assert client.post("/ask", data=data).status_code in (404, 410)


def test_invalid_scope(client, provider):
    a = upload(client, "a.txt", "Texto")
    assert client.post("/ask", data={"question": "x", "document_ids": [a]}).status_code == 422
    assert (
        client.post(
            "/ask", data={"question": "x", "mode": "rag", "document_ids": [a] * 21}
        ).status_code
        == 422
    )


def test_bm25_accent_and_exact_identifier():
    scores = bm25(
        "licitação AB123", ["Outro contrato sem identificador", "Licitacao AB123 aprovada"]
    )
    assert scores[1] > scores[0]


def test_rerank_prevents_long_document_dominating_context(client, provider):
    a = upload(client, "long.txt", " ".join(f"Secao {i} alfa " * 100 for i in range(40)))
    b = upload(client, "short.txt", "Outro documento beta.")
    response = client.post(
        "/ask", data={"question": "Compare", "mode": "rag", "document_ids": [a, b]}
    )
    assert response.status_code == 200, response.text
    assert {source["document_id"] for source in response.json()["sources"]} == {a, b}


def test_context_budget_drops_chunks_instead_of_overflowing(client, provider, monkeypatch):
    monkeypatch.setattr(settings, "ollama_max_context_chars", 200)
    a = upload(client, "long.txt", "x" * 2000)
    response = client.post("/ask", data={"question": "Compare", "mode": "rag", "document_ids": [a]})
    assert response.status_code == 422
    assert all(not request.url.path.endswith("chat/completions") for request in provider)


def test_query_filters_limit_sources_before_provider(client, provider):
    a = upload(client, "finance.txt", "Receita anual.")
    b = upload(client, "legal.txt", "Contrato anual.")
    client.patch("/documents/" + a, json={"category": "finance"})
    response = client.post(
        "/ask",
        data={
            "question": "Resumo",
            "mode": "rag",
            "document_ids": [a, b],
            "filters": json.dumps(
                {
                    "category": "finance",
                    "mime_type": "text/plain",
                    "created_from": "2000-01-01T00:00:00Z",
                }
            ),
        },
    )
    assert response.status_code == 200, response.text
    assert {source["document_id"] for source in response.json()["sources"]} == {a}
    assert b"Contrato anual" not in provider[-1].content
    assert (
        client.post(
            "/ask",
            data={
                "question": "x",
                "mode": "rag",
                "document_ids": [a],
                "filters": '{"unknown":true}',
            },
        ).status_code
        == 422
    )
