from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import ask, conversations, documents, feedback, health, interactions, stats
from app.core.config import settings
from app.core.logging import get_logger, setup_logging

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient() as client:
        app.state.http_client = client
        yield


app = FastAPI(
    lifespan=lifespan,
    title=settings.app_name,
    version="0.1.0",
    description="API de RAG com LLMOps",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(ask.router)
app.include_router(feedback.router)
app.include_router(interactions.router)
app.include_router(stats.router)
app.include_router(documents.router)
app.include_router(conversations.router)


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request, exc):
    get_logger(__name__).error("Falha na operacao de banco | path=%s", request.url.path)
    return JSONResponse(
        status_code=503, content={"detail": "Banco de dados indisponivel ou nao inicializado."}
    )


Instrumentator().instrument(app).expose(app)


@app.get("/")
async def root() -> dict:
    return {
        "app": settings.app_name,
        "env": settings.app_env,
        "docs": "/docs",
    }
