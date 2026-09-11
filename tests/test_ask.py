import base64
import json
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, settings
from app.core.database import get_db
from app.core.security import _requests
from app.main import app
from app.models import Base


class AskTests(unittest.TestCase):
    def setUp(self):
        _requests.clear()
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine)

        def override_db():
            with factory() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        self.addCleanup(engine.dispose)
        self.addCleanup(app.dependency_overrides.pop, get_db, None)
        self.key_patch = patch.object(settings, "gemini_api_key", SecretStr("test-secret"))
        self.key_patch.start()
        self.addCleanup(self.key_patch.stop)
        self.client = TestClient(app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.calls = []
        self.status = 200
        self.result = {
            "candidates": [
                {"finishReason": "STOP", "content": {"parts": [{"text": "Resposta do arquivo"}]}}
            ],
            "modelVersion": "test-model",
        }
        self.failure = None

        def handler(request):
            self.calls.append(request)
            if self.failure:
                raise self.failure
            return httpx.Response(self.status, json=self.result)

        self.transport_patch = patch.object(
            app.state.http_client, "_transport", httpx.MockTransport(handler)
        )
        self.transport_patch.start()
        self.addCleanup(self.transport_patch.stop)
        # Disable proxy mounts so all requests use the mock transport.
        self.mount_patch = patch.object(app.state.http_client, "_mounts", {})
        self.mount_patch.start()
        self.addCleanup(self.mount_patch.stop)

    def ask(self, name="document.txt", content=b"O total e 42", question="Qual o total?"):
        return self.client.post(
            "/ask",
            data={"question": question},
            files={"file": (name, content, "application/octet-stream")},
        )

    def test_text_request_and_response(self):
        response = self.ask()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "Resposta do arquivo")
        self.assertEqual(response.json()["sources"], [])
        self.assertEqual(response.json()["model_used"], "test-model")
        request = self.calls[0]
        self.assertEqual(request.headers["x-goog-api-key"], "test-secret")
        self.assertNotIn("test-secret", str(request.url))
        parts = json.loads(request.content)["contents"][0]["parts"]
        self.assertIn("O total e 42", parts[0]["text"])
        self.assertEqual(parts[1]["text"], "Qual o total?")

    def test_pdf_inline(self):
        content = b"%PDF-1.4\nexample"
        self.assertEqual(self.ask("doc.pdf", content).status_code, 200)
        part = json.loads(self.calls[0].content)["contents"][0]["parts"][0]["inlineData"]
        self.assertEqual(part["mimeType"], "application/pdf")
        self.assertEqual(base64.b64decode(part["data"]), content)

    def test_validation(self):
        for name, content, question, status in [
            ("doc.exe", b"x", "Pergunta", 415),
            ("doc.txt", b"", "Pergunta", 422),
            ("doc.txt", b"x", "   ", 422),
            ("doc.pdf", b"invalid", "Pergunta", 422),
            ("doc.txt", b"\xff", "Pergunta", 422),
            ("doc.txt", b"x", "x" * 2001, 422),
        ]:
            with self.subTest(name=name, question=question[:20]):
                self.assertEqual(self.ask(name, content, question).status_code, status)
        self.assertEqual(self.calls, [])

    def test_size_limit(self):
        with patch.object(settings, "max_upload_bytes", 4):
            self.assertEqual(self.ask(content=b"12345").status_code, 413)
            self.assertEqual(self.ask(content=b"1234").status_code, 200)

    def test_required_fields(self):
        self.assertEqual(self.client.post("/ask", data={"question": "Pergunta"}).status_code, 422)
        self.assertEqual(self.client.post("/ask", files={"file": ("a.txt", b"x")}).status_code, 422)

    def test_missing_key(self):
        with patch.object(settings, "gemini_api_key", SecretStr("")):
            self.assertEqual(self.ask().status_code, 503)
        self.assertEqual(self.calls, [])

    def test_upstream_errors_are_sanitized(self):
        for upstream, expected in [
            (400, 422),
            (401, 503),
            (403, 503),
            (429, 429),
            (500, 502),
            (404, 502),
            (503, 503),
            (504, 504),
        ]:
            with self.subTest(upstream=upstream):
                self.status = upstream
                self.result = {"error": {"message": "test-secret"}}
                response = self.ask()
                self.assertEqual(response.status_code, expected)
                self.assertNotIn("test-secret", response.text)
                if upstream == 503:
                    self.assertIn("temporariamente indisponivel", response.json()["detail"])

    def test_timeout_and_network(self):
        for failure, expected in [
            (httpx.ReadTimeout("secret"), 504),
            (httpx.ConnectError("secret"), 502),
        ]:
            self.failure = failure
            self.assertEqual(self.ask().status_code, expected)

    def test_invalid_and_blocked_responses(self):
        for result, expected in [
            ({}, 502),
            ([], 502),
            ({"candidates": []}, 502),
            ({"promptFeedback": {"blockReason": "SAFETY"}}, 422),
        ]:
            self.result = result
            self.assertEqual(self.ask().status_code, expected)

    def test_health_and_openapi(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        schema = self.client.get("/openapi.json").json()
        self.assertIn(
            "multipart/form-data", schema["paths"]["/ask"]["post"]["requestBody"]["content"]
        )

    def test_configured_gemini_key(self):
        config = Settings(_env_file=None, GEMINI_API_KEY="alias-key")
        self.assertEqual(config.gemini_api_key.get_secret_value(), "alias-key")


if __name__ == "__main__":
    unittest.main()
