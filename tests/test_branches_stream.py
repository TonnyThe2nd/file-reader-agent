import json

import httpx

from app.main import app
from tests.test_features import provider as provider_fixture

provider = provider_fixture


def test_branch_uses_fixed_prefix_without_copying_history(client, provider):
    first = client.post(
        "/ask",
        data={"question": "Primeira", "chat": "true"},
        files={"file": ("a.txt", b"Conteudo")},
    ).json()
    second = client.post(
        "/ask", data={"question": "Segunda", "conversation_id": first["conversation_id"]}
    ).json()
    branch = client.post(
        "/conversations/" + first["conversation_id"] + "/branches", json={"turn": 1}
    )
    assert branch.status_code == 201, branch.text
    branch_id = branch.json()["id"]
    detail = client.get("/conversations/" + branch_id).json()
    assert [m["question"] for m in detail["messages"]] == ["Primeira"]
    result = client.post("/ask", data={"question": "Outro caminho", "conversation_id": branch_id})
    assert result.status_code == 200, result.text
    assert result.json()["turn_number"] == 2
    messages = json.loads(provider[-1].content)["messages"]
    assert "Segunda" not in json.dumps(messages)
    assert client.get("/stats").json()["total_interactions"] == 3
    assert second["conversation_id"] != branch_id


def test_stream_persists_only_completed_response(client, monkeypatch):
    def handler(request):
        body = json.loads(request.content)
        assert body["stream"] is True
        events = [
            {"choices": [{"delta": {"content": "Ola "}}]},
            {
                "choices": [{"delta": {"content": "mundo"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
        ]
        return httpx.Response(
            200,
            text="".join("data: " + json.dumps(event) + "\n\n" for event in events)
            + "data: [DONE]\n\n",
        )

    monkeypatch.setattr(app.state.http_client, "_transport", httpx.MockTransport(handler))
    monkeypatch.setattr(app.state.http_client, "_mounts", {})
    response = client.post(
        "/ask", data={"question": "Teste", "stream": "true"}, files={"file": ("a.txt", b"Conteudo")}
    )
    assert response.status_code == 200
    assert "event: token" in response.text and "event: done" in response.text
    assert client.get("/interactions").json()[0]["answer"] == "Ola mundo"


def test_truncated_stream_not_saved(client, monkeypatch):
    monkeypatch.setattr(
        app.state.http_client,
        "_transport",
        httpx.MockTransport(
            lambda _: httpx.Response(
                200, text='data: {"choices":[{"delta":{"content":"Parcial"}}]}\n\n'
            )
        ),
    )
    monkeypatch.setattr(app.state.http_client, "_mounts", {})
    response = client.post(
        "/ask", data={"question": "Teste", "stream": "true"}, files={"file": ("a.txt", b"Conteudo")}
    )
    assert "event: error" in response.text and "event: done" not in response.text
    assert client.get("/interactions").json() == []
