from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models import Feedback, Interaction


def add_interaction(database, latency=100, created_at=None, answer="Resposta"):
    with database() as db:
        interaction = Interaction(
            question="Pergunta",
            answer=answer,
            sources=[],
            latency_ms=latency,
            model_used="test-model",
            cache_hit=False,
        )
        if created_at is not None:
            interaction.created_at = created_at
        db.add(interaction)
        db.commit()
        return str(interaction.id)


def test_feedback_is_persisted(client, database):
    interaction_id = add_interaction(database)
    response = client.post(
        "/feedback", json={"interaction_id": interaction_id, "rating": 1, "comment": "Util"}
    )
    assert response.status_code == 200
    with database() as db:
        feedback = db.scalar(select(Feedback))
        assert str(feedback.interaction_id) == interaction_id
        assert feedback.rating == 1
        assert feedback.comment == "Util"
        assert feedback.interaction.question == "Pergunta"


def test_missing_interaction_and_duplicate_feedback(client, database):
    assert (
        client.post("/feedback", json={"interaction_id": str(uuid4()), "rating": 1}).status_code
        == 404
    )
    interaction_id = add_interaction(database)
    payload = {"interaction_id": interaction_id, "rating": -1}
    assert client.post("/feedback", json=payload).status_code == 200
    assert client.post("/feedback", json=payload).status_code == 409
    with database() as db:
        assert len(db.scalars(select(Feedback)).all()) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"interaction_id": "invalid", "rating": 1},
        {"interaction_id": str(uuid4()), "rating": 0},
        {"interaction_id": str(uuid4()), "rating": 2},
    ],
)
def test_feedback_validation(client, payload):
    assert client.post("/feedback", json=payload).status_code == 422


def test_empty_stats(client):
    response = client.get("/stats")
    assert response.status_code == 200
    assert response.json() == dict(
        total_interactions=0,
        total_feedbacks=0,
        positive_feedbacks=0,
        negative_feedbacks=0,
        positive_rate=0.0,
        avg_latency_ms=0.0,
        avg_latency_ms_last_24h=0.0,
    )


def test_stats_aggregates(client, database):
    now = datetime.now(timezone.utc)
    first = add_interaction(database, 100, now - timedelta(days=2))
    second = add_interaction(database, 200, now - timedelta(hours=2))
    add_interaction(database, 300, now - timedelta(hours=1))
    assert client.post("/feedback", json={"interaction_id": first, "rating": 1}).status_code == 200
    assert (
        client.post("/feedback", json={"interaction_id": second, "rating": -1}).status_code == 200
    )
    response = client.get("/stats")
    assert response.status_code == 200
    assert response.json() == dict(
        total_interactions=3,
        total_feedbacks=2,
        positive_feedbacks=1,
        negative_feedbacks=1,
        positive_rate=50.0,
        avg_latency_ms=200.0,
        avg_latency_ms_last_24h=250.0,
    )


def test_history_pagination_and_truncation(client, database):
    now = datetime.now(timezone.utc)
    oldest = add_interaction(database, created_at=now - timedelta(days=1))
    newest = add_interaction(database, created_at=now, answer="a" * 300)
    response = client.get("/interactions?limit=1")
    assert response.status_code == 200
    assert response.json()[0]["id"] == newest
    assert len(response.json()[0]["answer"]) == 200
    assert client.get("/interactions?limit=1&offset=1").json()[0]["id"] == oldest
    assert client.get("/interactions?offset=2").json() == []
    for query in ("limit=0", "limit=101", "offset=-1"):
        assert client.get("/interactions?" + query).status_code == 422


def test_cascade_delete(client, database):
    interaction_id = add_interaction(database)
    client.post("/feedback", json={"interaction_id": interaction_id, "rating": 1})
    with database() as db:
        interaction = db.scalar(select(Interaction))
        db.delete(interaction)
        db.commit()
        assert db.scalar(select(Feedback)) is None
