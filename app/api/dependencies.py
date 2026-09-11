from fastapi import Request

from app.core.config import settings
from app.services.gemini_service import GeminiService
from app.services.rag_service import RAGService


def get_rag_service(request: Request) -> RAGService:
    return RAGService(GeminiService(request.app.state.http_client, settings))
