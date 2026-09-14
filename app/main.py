import time
from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import (
    admin,
    analytics,
    ask,
    conversations,
    documents,
    feedback,
    health,
    interactions,
    stats,
)
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.core.security import current_owner

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
app.include_router(admin.router)
app.include_router(analytics.router)


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request, exc):
    get_logger(__name__).error("Falha na operacao de banco | path=%s", request.url.path)
    return JSONResponse(
        status_code=503, content={"detail": "Banco de dados indisponivel ou nao inicializado."}
    )


Instrumentator().instrument(app).expose(app, dependencies=[Depends(current_owner)])


@app.middleware("http")
async def request_trace(request, call_next):
    request_id = str(uuid4())
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["Cache-Control"] = "no-store"
    route = getattr(request.scope.get("route"), "path", "unmatched")
    get_logger(__name__).info(
        "method=%s route=%s status=%s headers_latency_ms=%.1f",
        request.method,
        route,
        response.status_code,
        (time.perf_counter() - start) * 1000,
        extra={"request_id": request_id},
    )
    return response


@app.get("/")
async def root() -> dict:
    return {
        "app": settings.app_name,
        "env": settings.app_env,
        "docs": "/docs",
    }
