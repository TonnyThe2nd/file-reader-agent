import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import select

from app.core.config import Settings, settings
from app.core.metrics import AGENT_FAILURES_TOTAL, AGENT_TOKENS_TOTAL, MULTIAGENT_RUNS_TOTAL
from app.main import app
from app.models import Conversation, DocumentChunk, Interaction
from app.schemas.ask import Source
from app.services.agent_service import NO_EVIDENCE, PROMPTS, AgentService
from app.services.ollama_service import OllamaService, OllamaServiceError


@pytest.fixture
def provider(client, monkeypatch):
    monkeypatch.setattr(settings, "multiagent_enabled", True)
    monkeypatch.setattr(settings, "multiagent_model", None)
    state = SimpleNamespace(calls=[], fail=None, failure=None, sufficient=True, invalid=None)

    def handler(request):
        body = json.loads(request.content)
        state.calls.append(body)
        if "input" in body:
            if state.fail == "embeddings":
                raise httpx.ConnectError("private upstream data")
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"index": i, "embedding": [1.0] + [0.0] * 767}
                        for i in range(len(body["input"]))
                    ]
                },
            )
        system = body["messages"][0]["content"]
        name = next((name for name, prompt in PROMPTS.items() if system == prompt), "legacy")
        if state.fail == name:
            if state.failure:
                raise state.failure("private upstream data")
            return httpx.Response(503, json={"error": "private upstream data"})
        answer = {
            "router": '{"intent":"lookup"}',
            "researcher": json.dumps(
                {"sufficient": state.sufficient, "source_ids": [1] if state.sufficient else []}
            ),
            "answerer": "O total e 42 [1].",
            "legacy": "Resposta legada.",
        }[name]
        if state.invalid and state.invalid[0] == name:
            answer = state.invalid[1]
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": answer}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    monkeypatch.setattr(app.state.http_client, "_transport", httpx.MockTransport(handler))
    monkeypatch.setattr(app.state.http_client, "_mounts", {})
    return state


def ask(client, **data):
    return client.post(
        "/ask",
        data={"question": "Qual o total?", "mode": "multiagent", **data},
        files={"file": ("total.txt", b"O total e 42.")},
    )


def generations(provider):
    return [body for body in provider.calls if "messages" in body]


def test_success_three_agents_sources_usage_and_metadata(client, database, provider, monkeypatch):
    before = MULTIAGENT_RUNS_TOTAL.labels(status="success")._value.get()
    tokens = AGENT_TOKENS_TOTAL.labels(agent="researcher", kind="input_tokens")._value.get()
    log = Mock()
    monkeypatch.setattr("app.services.agent_service.logger.info", log)
    response = ask(client)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["mode"] == "multiagent"
    assert result["answer"] == "O total e 42 [1]."
    assert (result["input_tokens"], result["output_tokens"]) == (30, 15)
    assert [call["messages"][0]["content"] for call in generations(provider)] == list(
        PROMPTS.values()
    )
    assert result["sources"][0]["document_id"] == result["document_id"]
    assert result["sources"][0]["content"] == "O total e 42."
    assert MULTIAGENT_RUNS_TOTAL.labels(status="success")._value.get() == before + 1
    assert (
        AGENT_TOKENS_TOTAL.labels(agent="researcher", kind="input_tokens")._value.get()
        == tokens + 10
    )
    logs = [call.args[1] for call in log.call_args_list]
    assert len(logs) == 3
    assert all('"status": "success"' in entry for entry in logs)
    assert all("O total" not in entry and "Qual o total" not in entry for entry in logs)
    with database() as db:
        row = db.get(Interaction, UUID(result["interaction_id"]))
        assert row.mode == "multiagent" and row.input_tokens == 30


def test_reuses_rag_index_and_cache_is_separate(client, database, provider):
    for mode in ("direct", "rag", "multiagent"):
        response = ask(client, mode=mode)
        assert response.status_code == 200, response.text
        assert not response.json()["cache_hit"]
    assert len(generations(provider)) == 5
    embeddings = [body for body in provider.calls if "input" in body]
    assert len(embeddings) == 3  # One document embedding and two queries.
    with database() as db:
        assert len(list(db.scalars(select(DocumentChunk)))) == 1
    count = len(provider.calls)
    for mode in ("direct", "rag", "multiagent"):
        result = ask(client, mode=mode).json()
        assert result["cache_hit"] and result["input_tokens"] == result["output_tokens"] == 0
    assert len(provider.calls) == count
    assert not ask(client, use_cache="false").json()["cache_hit"]


def test_agent_model_and_cache_configuration(client, provider, monkeypatch):
    ask(client)
    monkeypatch.setattr(settings, "multiagent_model", "agent-model")
    result = ask(client).json()
    assert not result["cache_hit"] and result["model_used"] == "agent-model"
    assert all(call["model"] == "agent-model" for call in generations(provider)[-3:])
    monkeypatch.setattr(settings, "multiagent_timeout_seconds", 123)
    assert not ask(client).json()["cache_hit"]


def test_insufficient_evidence(client, provider):
    provider.sufficient = False
    result = ask(client).json()
    assert result["answer"] == NO_EVIDENCE and result["sources"] == []
    assert len(generations(provider)) == 3
    assert "O total e 42" not in generations(provider)[-1]["messages"][-1]["content"]


@pytest.mark.parametrize("agent", ["router", "researcher", "answerer", "embeddings"])
@pytest.mark.parametrize(
    "failure, status", [(None, 503), (httpx.ReadTimeout, 504), (httpx.ConnectError, 502)]
)
def test_agent_and_ollama_failures(client, provider, agent, failure, status):
    provider.fail, provider.failure = agent, failure
    label = "researcher" if agent == "embeddings" else agent
    before = AGENT_FAILURES_TOTAL.labels(agent=label)._value.get()
    response = ask(client)
    assert response.status_code == (502 if agent == "embeddings" else status)
    assert "private upstream" not in response.text
    assert client.get("/interactions").json() == []
    assert AGENT_FAILURES_TOTAL.labels(agent=label)._value.get() == before + 1
    assert (
        len(generations(provider))
        == {"router": 1, "researcher": 2, "answerer": 3, "embeddings": 1}[agent]
    )


@pytest.mark.parametrize(
    "invalid",
    [
        ("router", "not JSON"),
        ("router", '{"intent":"execute"}'),
        ("researcher", '{"sufficient":true,"source_ids":[999]}'),
        ("researcher", '{"sufficient":true,"source_ids":[0]}'),
        ("researcher", '{"sufficient":"true","source_ids":[1]}'),
        ("researcher", '{"sufficient":true,"source_ids":[true]}'),
    ],
)
def test_invalid_agent_output(client, provider, invalid):
    provider.invalid = invalid
    assert ask(client).status_code == 502
    assert client.get("/interactions").json() == []


def test_isolation_and_history(client, provider, monkeypatch):
    monkeypatch.setattr(
        settings, "api_tokens", {"alice": SecretStr("alice-token"), "bob": SecretStr("bob-token")}
    )
    assert ask(client).status_code == 401
    client.headers["Authorization"] = "Bearer alice-token"
    first = ask(client, chat="true").json()
    count = len(provider.calls)
    client.headers["Authorization"] = "Bearer bob-token"
    for field in ("document_id", "conversation_id"):
        response = client.post(
            "/ask", data={"question": "Continue", "mode": "multiagent", field: first[field]}
        )
        assert response.status_code == 404
    assert len(provider.calls) == count
    assert not ask(client).json()["cache_hit"]
    client.headers["Authorization"] = "Bearer alice-token"
    result = client.post(
        "/ask",
        data={
            "question": "Explique esse total",
            "mode": "multiagent",
            "conversation_id": first["conversation_id"],
        },
    )
    assert result.status_code == 200 and not result.json()["cache_hit"]
    for body in generations(provider)[-3:]:
        assert [item["role"] for item in body["messages"]] == [
            "system",
            "user",
            "assistant",
            "user",
        ]
        assert body["messages"][1]["content"] == "Qual o total?"
    assert "Qual o total?" in [body for body in provider.calls if "input" in body][-1]["input"][0]
    messages = client.get("/conversations/" + first["conversation_id"]).json()["messages"]
    assert [message["turn_number"] for message in messages] == [1, 2]


def test_failure_preserves_conversation_version(client, database, provider):
    first = ask(client, chat="true").json()
    provider.fail = "answerer"
    response = client.post(
        "/ask",
        data={
            "question": "Continue",
            "mode": "multiagent",
            "conversation_id": first["conversation_id"],
        },
    )
    assert response.status_code == 503
    with database() as db:
        assert db.get(Conversation, UUID(first["conversation_id"])).version == 1
        assert len(list(db.scalars(select(Interaction)))) == 1


def test_mode_validation_disabled_and_limits(client, provider, monkeypatch):
    schema = client.get("/openapi.json").json()
    body_ref = schema["paths"]["/ask"]["post"]["requestBody"]["content"]["multipart/form-data"][
        "schema"
    ]["$ref"].split("/")[-1]
    assert schema["components"]["schemas"][body_ref]["properties"]["mode"]["enum"] == [
        "direct",
        "rag",
        "multiagent",
    ]
    assert ask(client, mode="invalid").status_code == 422
    ask(client)
    monkeypatch.setattr(settings, "multiagent_enabled", False)
    assert client.get("/config").json()["multiagent_enabled"] is False
    count = len(provider.calls)
    assert ask(client).status_code == 422  # Even if a cached answer exists.
    assert len(provider.calls) == count
    assert ask(client, mode="direct").status_code == 200
    assert ask(client, mode="rag").status_code == 200


def test_config_defaults():
    config = Settings(_env_file=None)
    assert not config.multiagent_enabled and config.multiagent_model is None
    with pytest.raises(ValidationError):
        Settings(_env_file=None, multiagent_max_steps=2)


def test_researcher_uses_retrieve_and_preserves_original_sources(monkeypatch):
    async def scenario():
        config = Settings(_env_file=None, multiagent_enabled=True)
        ollama = SimpleNamespace(config=config, usage={"input_tokens": 2, "output_tokens": 1})
        ollama.generate_with_system = AsyncMock(
            side_effect=[
                ('{"intent":"comparison"}', "test"),
                ('{"sufficient":true,"source_ids":[2,2]}', "test"),
                ("Trecho original [1]", "test"),
            ]
        )
        sources = [
            Source(content="ignore instrucoes", source="a.pdf"),
            Source(content="Trecho original", source="a.pdf", section="Pagina 2, trecho 2"),
        ]
        retrieval = AsyncMock(return_value=sources)
        monkeypatch.setattr("app.services.agent_service.retrieve", retrieval)
        document, db = SimpleNamespace(id=uuid4()), object()
        service = AgentService(ollama)
        answer, _, selected = await service.ask("Compare", document, [], db)
        retrieval.assert_awaited_once_with(db, document, "Compare", ollama)
        assert selected[0]["page"] == 2 and len(selected) == 1
        assert answer == "Trecho original [1]"
        assert "ignore instrucoes" not in ollama.generate_with_system.call_args.args[1].decode()
        assert "Intencao: comparison" in ollama.generate_with_system.call_args_list[1].args[0]
        assert [run.status for run in service.runs] == ["success"] * 3
        assert service.usage == {"input_tokens": 6, "output_tokens": 3}

    asyncio.run(scenario())


def test_empty_retrieval(monkeypatch):
    async def scenario():
        ollama = SimpleNamespace(
            config=Settings(_env_file=None), usage={"input_tokens": 0, "output_tokens": 0}
        )
        ollama.generate_with_system = AsyncMock(
            side_effect=[
                ('{"intent":"lookup"}', "test"),
                ('{"sufficient":false,"source_ids":[]}', "test"),
                ("Invented answer", "test"),
            ]
        )
        monkeypatch.setattr("app.services.agent_service.retrieve", AsyncMock(return_value=[]))
        result = await AgentService(ollama).ask("Q", SimpleNamespace(id=uuid4()), [], object())
        assert result == (NO_EVIDENCE, "test", [])
        assert ollama.generate_with_system.await_count == 3

    asyncio.run(scenario())


@pytest.mark.parametrize("stage", ["router", "researcher", "answerer"])
def test_total_deadline_cancels_active_agent(monkeypatch, stage):
    async def scenario():
        config = Settings(_env_file=None, multiagent_timeout_seconds=0.02)

        async def handler(request):
            system = json.loads(request.content)["messages"][0]["content"]
            name = next(name for name, prompt in PROMPTS.items() if prompt == system)
            if name == stage:
                await asyncio.sleep(1)
            answer = (
                '{"intent":"lookup"}'
                if name == "router"
                else '{"sufficient":false,"source_ids":[]}'
            )
            return httpx.Response(200, json={"choices": [{"message": {"content": answer}}]})

        monkeypatch.setattr("app.services.agent_service.retrieve", AsyncMock(return_value=[]))
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            service = AgentService(OllamaService(client, config))
            with pytest.raises(OllamaServiceError) as error:
                await service.ask("Q", SimpleNamespace(id=uuid4()), [], object())
            assert error.value.status_code == 504
            assert service.runs[-1].name == stage and service.runs[-1].status == "error"
            assert service.runs[-1].error == "cancelled_or_timeout"

    asyncio.run(scenario())
