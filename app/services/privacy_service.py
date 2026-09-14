"""Deterministic local redaction; not a general PII classifier."""

import re

_PATTERNS = (
    (r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[EMAIL]"),
    (r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", "[CPF]"),
    (r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b", "[CNPJ]"),
    (r"(?i)\b(?:bearer|api[_-]?key|password|senha)\s*[:= ]\s*[\w./+\-=]{6,}", "[SEGREDO]"),
    (r"(?<!\d)(?:\+55\s*)?\(?\d{2}\)?\s*9?\d{4}[- ]\d{4}(?!\d)", "[TELEFONE]"),
)


def redact(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text
