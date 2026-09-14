import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import timezone
from uuid import UUID

from app.core.config import settings
from app.schemas.ask import Source
from app.services.document_service import cosine, index_document

RETRIEVAL_VERSION = "hybrid-rrf-mmr-v1"
STOPWORDS = set("a o as os de da do das dos e em um uma para por que qual quais com no na".split())


@dataclass(frozen=True)
class DocumentReference:
    id: UUID
    name: str


@dataclass(frozen=True)
class ChunkReference:
    position: int
    section: str
    content: str
    embedding: list[float]


def terms(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    return [t for t in re.findall(r"\w+", normalized) if t not in STOPWORDS]


def filter_documents(documents, filters):
    from fastapi import HTTPException

    def utc(value):
        return (
            value.replace(tzinfo=timezone.utc)
            if value.tzinfo is None
            else value.astimezone(timezone.utc)
        )

    start = utc(filters.created_from) if filters.created_from else None
    end = utc(filters.created_to) if filters.created_to else None
    if start and end and start > end:
        raise HTTPException(422, "Intervalo de datas invalido.")
    result = [
        document
        for document in documents
        if (filters.category is None or document.category == filters.category)
        and (filters.mime_type is None or document.mime_type == filters.mime_type)
        and (start is None or utc(document.created_at) >= start)
        and (end is None or utc(document.created_at) <= end)
    ]
    if not result:
        raise HTTPException(422, "Nenhum documento selecionado corresponde aos filtros.")
    return result


def bm25(question: str, texts: list[str]) -> list[float]:
    counts = [Counter(terms(text)) for text in texts]
    lengths = [sum(c.values()) for c in counts]
    average = sum(lengths) / max(len(lengths), 1) or 1
    scores = [0.0] * len(texts)
    for term in set(terms(question)):
        frequency = sum(term in c for c in counts)
        if not frequency:
            continue
        idf = math.log(1 + (len(texts) - frequency + 0.5) / (frequency + 0.5))
        for i, count in enumerate(counts):
            tf = count[term]
            scores[i] += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * lengths[i] / average))
    return scores


async def retrieve_many(db, documents, question, ollama, *, hybrid=True, rerank=True):
    entries = []
    for document in documents:
        chunks = await index_document(db, document, ollama)
        reference = DocumentReference(document.id, document.name)
        entries.extend(
            (
                reference,
                ChunkReference(chunk.position, chunk.section, chunk.content, chunk.embedding),
            )
            for chunk in chunks
        )
    vector = (await ollama.embed([question], "RETRIEVAL_QUERY"))[0]
    semantic = [cosine(vector, chunk.embedding) for _, chunk in entries]
    lexical = bm25(question, [chunk.content for _, chunk in entries])
    order = sorted(range(len(entries)), key=lambda i: (-semantic[i], i))
    scores = {i: 1 / (60 + rank) for rank, i in enumerate(order, 1)}
    if hybrid:
        for rank, i in enumerate(sorted(order, key=lambda i: (-lexical[i], i)), 1):
            if lexical[i] > 0:
                scores[i] += 1 / (60 + rank)
    candidates = sorted(order, key=lambda i: (-scores[i], i))[: max(40, settings.rag_top_k * 4)]
    # Preserve each document's best candidate when a long file dominates the pool.
    for document in documents:
        best = next(
            (
                i
                for i in sorted(order, key=lambda i: (-scores[i], i))
                if entries[i][0].id == document.id
            ),
            None,
        )
        if best is not None and best not in candidates:
            candidates.append(best)
    selected = []
    per_document_limit = math.ceil(settings.rag_top_k / len(documents))
    remaining = settings.ollama_max_context_chars
    maximum = max(scores.values(), default=1)
    while candidates and len(selected) < settings.rag_top_k:

        def relevance(i):
            redundancy = max(
                (
                    max(0, cosine(entries[i][1].embedding, entries[j][1].embedding))
                    for j in selected
                ),
                default=0,
            )
            same_document = any(entries[i][0].id == entries[j][0].id for j in selected)
            return (
                0.7 * scores[i] / maximum - 0.15 * redundancy - 0.15 * same_document
                if rerank
                else scores[i]
            )

        best = max(candidates, key=lambda i: (relevance(i), -i))
        candidates.remove(best)
        document, chunk = entries[best]
        if rerank and sum(entries[j][0].id == document.id for j in selected) >= per_document_limit:
            continue
        # Identical text in different files remains useful evidence for comparisons.
        if rerank and any(
            document.id == entries[j][0].id and chunk.content == entries[j][1].content
            for j in selected
        ):
            continue
        size = len(chunk.content) + len(document.name) + len(chunk.section) + 50
        if size > remaining:
            continue
        selected.append(best)
        remaining -= size
    return [
        Source(
            document_id=str(entries[i][0].id),
            source=entries[i][0].name,
            content=entries[i][1].content,
            section=f"{entries[i][1].section}, trecho {entries[i][1].position + 1}",
            page=int(entries[i][1].section.split()[1])
            if entries[i][1].section.startswith("Pagina ")
            else None,
            score=scores[i],
        )
        for i in selected
    ]
