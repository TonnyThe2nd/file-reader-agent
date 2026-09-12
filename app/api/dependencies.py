from fastapi import Request

from app.core.config import settings
from app.services.ollama_service import OllamaService
from app.services.rag_service import RAGService


def get_rag_service(request: Request) -> RAGService:
    return RAGService(OllamaService(request.app.state.http_client, settings))
