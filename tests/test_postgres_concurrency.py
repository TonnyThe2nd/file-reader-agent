"""Optional real PostgreSQL checks, isolated in a disposable schema."""

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.governance import UserPolicy
from app.services.document_service import save_document
from app.services.governance_service import reserve_query
from app.worker import claim


@pytest.fixture
def postgres_factory():
    url = os.environ.get("POSTGRES_TEST_URL")
    if not url:
        pytest.skip("POSTGRES_TEST_URL is not configured")
    schema = "product_test_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {schema}"))
    scoped_url = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(scoped_url)
    try:
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine)
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def test_atomic_query_quota_postgres(postgres_factory):
    with postgres_factory() as db:
        db.add(UserPolicy(owner_id="local", role="user", teams=[], daily_queries=1))
        db.commit()

    def reserve(_):
        with postgres_factory() as db:
            try:
                reserve_query(db, "local", 100)
                return 200
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reserve, range(2))) == [200, 429]


def test_storage_quota_serializes_uploads_postgres(postgres_factory):
    with postgres_factory() as db:
        db.add(UserPolicy(owner_id="local", role="user", teams=[], storage_bytes=100))
        db.commit()

    def upload(value):
        with postgres_factory() as db:
            try:
                save_document(db, "local", "a.txt", value * 60, "text/plain")
                return 200
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(upload, [b"a", b"b"])) == [200, 413]


def test_workers_claim_distinct_documents_postgres(postgres_factory):
    with postgres_factory() as db:
        for value in (b"first", b"second"):
            save_document(db, "local", "a.txt", value, "text/plain")
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = list(pool.map(lambda _: claim(postgres_factory), range(2)))
    assert jobs[0] and jobs[1] and jobs[0][0] != jobs[1][0]


def test_duplicate_uploads_share_quota_postgres(postgres_factory):
    with postgres_factory() as db:
        db.add(UserPolicy(owner_id="local", role="user", teams=[], storage_bytes=100))
        db.commit()

    def upload(_):
        with postgres_factory() as db:
            return save_document(db, "local", "a.txt", b"a" * 60, "text/plain").id

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(upload, range(2)))
    assert ids[0] == ids[1]
