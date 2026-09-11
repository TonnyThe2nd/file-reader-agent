"""Identidades configuradas pelo operador; nunca aceita o owner enviado pelo cliente."""

import secrets
import time
from collections import deque
from threading import Lock
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

bearer = HTTPBearer(auto_error=False)
_requests: dict[str, deque] = {}
_lock = Lock()


def current_owner(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> str:
    if not settings.api_tokens:
        if settings.app_env != "development":
            raise HTTPException(503, "O acesso precisa ser configurado!")
        return "local"
    if credentials:
        for owner, token in settings.api_tokens.items():
            if secrets.compare_digest(
                credentials.credentials.encode("utf-8"), token.get_secret_value().encode("utf-8")
            ):
                return owner
    raise HTTPException(
        401, "Chave de acesso invalida ou ausente.", headers={"WWW-Authenticate": "Bearer"}
    )


def limit_requests(owner: Annotated[str, Depends(current_owner)]) -> str:
    now = time.monotonic()
    with _lock:
        queue = _requests.setdefault(owner, deque())
        while queue and queue[0] <= now - 60:
            queue.popleft()
        if len(queue) >= settings.rate_limit_per_minute:
            raise HTTPException(
                429,
                "Limite de consultas atingido.",
                headers={"Retry-After": "60"},
            )
        queue.append(now)
    return owner
