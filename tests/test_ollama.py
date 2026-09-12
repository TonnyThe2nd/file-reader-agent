import asyncio
import json

import httpx
import pytest

from app.core.config import Settings
from app.services.ollama_service import OllamaService, OllamaServiceError


def run_service(handler, action, **config):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await action(OllamaService(client, Settings(_env_file=None, **config)))

    return asyncio.run(run())


def test_embeddings_batch_order_and_prefixes():
    calls = []

    def handler(request):
        payload = json.loads(request.content)
        calls.append(payload)
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": i, "embedding": [float(i + 1), 1.0]}
                    for i in reversed(range(len(payload["input"])))
                ]
            },
        )

    result = run_service(
        handler,
        lambda s: s.embed(["texto"] * 33, "RETRIEVAL_DOCUMENT"),
        ollama_embedding_dimensions=2,
    )
    assert len(result) == 33 and result[0] == [1, 1] and result[31] == [32, 1]
    assert [len(c["input"]) for c in calls] == [32, 1]
    assert calls[0]["input"][0] == "search_document: texto"
    run_service(
        handler, lambda s: s.embed(["pergunta"], "RETRIEVAL_QUERY"), ollama_embedding_dimensions=2
    )
    assert calls[-1]["input"] == ["search_query: pergunta"]


@pytest.mark.parametrize(
    "data",
    [
        {"data": [{"index": 0, "embedding": [0, 0]}]},
        {"data": [{"index": 1, "embedding": [1, 0]}]},
        {"data": [{"index": 0, "embedding": [1]}]},
        {"data": None},
    ],
)
def test_invalid_embeddings(data):
    with pytest.raises(OllamaServiceError) as exc:
        run_service(
            lambda _: httpx.Response(200, json=data),
            lambda s: s.embed(["x"], "RETRIEVAL_QUERY"),
            ollama_embedding_dimensions=2,
        )
    assert exc.value.status_code == 502


def test_truncated_generation_rejected():
    with pytest.raises(OllamaServiceError) as exc:
        run_service(
            lambda _: httpx.Response(
                200,
                json={
                    "choices": [{"finish_reason": "length", "message": {"content": "incompleta"}}]
                },
            ),
            lambda s: s.generate("pergunta", b"texto", "text/plain"),
        )
    assert exc.value.status_code == 502


def test_zero_temperature_and_image_payload():
    def handler(request):
        payload = json.loads(request.content)
        assert payload["temperature"] == 0
        assert (
            payload["messages"][-1]["content"][1]["image_url"]["url"]
            == "data:image/png;base64,eA=="
        )
        return httpx.Response(200, json={"choices": [{"message": {"content": "resposta"}}]})

    assert (
        run_service(
            handler, lambda s: s.generate("pergunta", b"x", "image/png"), OLLAMA_TEMPERATURE=0
        )[0]
        == "resposta"
    )


def test_direct_context_limit_does_not_call_provider():
    def handler(_):
        pytest.fail("Nao deve enviar documento acima do limite")

    with pytest.raises(OllamaServiceError) as exc:
        run_service(
            handler,
            lambda s: s.generate("pergunta", b"texto", "text/plain"),
            ollama_max_context_chars=2,
        )
    assert exc.value.status_code == 413
