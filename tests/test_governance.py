import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

from pydantic import SecretStr

from app.core.config import settings
from app.models import Document
from app.models.governance import UserPolicy
from app.services.retention_service import apply_retention
from tests.test_features import provider as provider_fixture

provider = provider_fixture


def identities(client, monkeypatch):
    monkeypatch.setattr(
        settings,
        "api_tokens",
        {name: SecretStr(name + "-secret") for name in ("alice", "bob", "admin")},
    )
    monkeypatch.setattr(settings, "admin_owners", ["admin"])
    client.headers["Authorization"] = "Bearer admin-secret"
    for name, role in [("alice", "manager"), ("bob", "user")]:
        assert (
            client.put(
                "/admin/users/" + name, json={"role": role, "teams": ["finance"]}
            ).status_code
            == 200
        )


def test_team_sharing_revocation_and_write_isolation(client, monkeypatch, provider):
    identities(client, monkeypatch)
    client.headers["Authorization"] = "Bearer alice-secret"
    document = client.post("/documents", files={"file": ("a.txt", b"Financeiro")}).json()
    grant = client.post(
        "/documents/" + document["id"] + "/grants", json={"kind": "team", "recipient": "finance"}
    ).json()
    client.headers["Authorization"] = "Bearer bob-secret"
    assert client.get("/documents/" + document["id"]).status_code == 200
    assert len(client.get("/documents").json()) == 1
    assert client.delete("/documents/" + document["id"]).status_code == 404
    assert client.patch("/documents/" + document["id"], json={"category": "x"}).status_code == 404
    data = {"question": "Resumo", "mode": "rag", "document_id": document["id"]}
    assert client.post("/ask", data=data).status_code == 200
    assert client.get("/admin/users").status_code == 403
    assert client.get("/analytics?team=finance").status_code == 403
    client.headers["Authorization"] = "Bearer alice-secret"
    assert (
        client.delete("/documents/" + document["id"] + "/grants/" + grant["id"]).status_code == 204
    )
    client.headers["Authorization"] = "Bearer bob-secret"
    assert client.post("/ask", data=data).status_code == 404  # cache also reauthorizes
    assert client.get("/documents").json() == []


def test_quota_and_admin_policy(client, monkeypatch, provider):
    identities(client, monkeypatch)
    assert (
        client.put("/admin/users/bob", json={"daily_queries": 1, "storage_bytes": 20}).status_code
        == 200
    )
    client.headers["Authorization"] = "Bearer bob-secret"
    assert client.post("/documents", files={"file": ("large.txt", b"x" * 21)}).status_code == 413
    document = client.post("/documents", files={"file": ("a.txt", b"123")}).json()
    data = {"question": "Resumo", "document_id": document["id"]}
    assert client.post("/ask", data=data).status_code == 200
    assert client.post("/ask", data=data).status_code == 429
    assert all(row["owner"] == "bob" for row in client.get("/audit").json())


def test_redaction_before_embeddings_and_generation(client, monkeypatch, provider):
    monkeypatch.setattr(settings, "redact_sensitive_data", True)
    response = client.post(
        "/ask",
        data={"question": "Contato maria@example.com?", "mode": "rag"},
        files={"file": ("a.txt", b"CPF 123.456.789-00; maria@example.com; senha=secret123")},
    )
    assert response.status_code == 200, response.text
    for request in provider:
        payload = json.dumps(json.loads(request.content))
        assert "maria@example.com" not in payload
        assert "123.456.789-00" not in payload
        assert "secret123" not in payload


def test_retention_purges_related_queries_and_preserves_audit(client, database, provider):
    answer = client.post(
        "/ask", data={"question": "Resumo"}, files={"file": ("a.txt", b"Conteudo")}
    ).json()
    with database() as db:
        row = db.get(Document, UUID(answer["document_id"]))
        row.created_at = datetime.now(timezone.utc) - timedelta(days=10)
        limits = db.get(UserPolicy, "local")
        limits.retention_days = 5
        db.commit()
        assert apply_retention(db)["documents"] == 1
        assert db.get(Document, row.id) is not None
        assert apply_retention(db, dry_run=False)["documents"] == 1
    assert client.get("/documents").json() == []
    assert client.get("/interactions").json() == []


def test_analytics_document_tracking(client, provider):
    answer = client.post(
        "/ask", data={"question": "Resumo", "mode": "rag"}, files={"file": ("a.txt", b"Conteudo")}
    ).json()
    metrics = client.get("/analytics").json()
    assert metrics["documents"][0]["id"] == answer["document_id"]
    assert metrics["total_tokens"] == 52
    assert metrics["daily_queries"] == 1


def test_history_filters_include_secondary_document(client, provider):
    ids = [
        client.post("/documents", files={"file": (name, content)}).json()["id"]
        for name, content in [("a.txt", b"Primeiro"), ("b.txt", b"Segundo")]
    ]
    response = client.post(
        "/ask", data={"question": "Compare", "mode": "rag", "document_ids": ids}
    ).json()
    secondary = response["document_ids"][1]
    assert (
        len(client.get("/interactions", params={"mode": "rag", "document_id": secondary}).json())
        == 1
    )
    assert client.get("/interactions?mode=direct").json() == []
    assert client.get("/interactions?created_from=2099-01-01T00:00:00Z").json() == []
