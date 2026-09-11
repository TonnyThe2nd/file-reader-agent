from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command
from app.models import Base


def test_upgrade_preserves_legacy_rows_and_matches_models(tmp_path, monkeypatch):
    from app.core.config import settings

    url = "sqlite:///" + str(tmp_path / "migration.db").replace("\\", "/")
    monkeypatch.setattr(settings, "database_url", url)
    config = Config("alembic.ini")
    command.upgrade(config, "ace48b94f7c9")
    engine = create_engine(url)
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO interactions (id,question,answer,sources,latency_ms,model_used,cache_hit,created_at) VALUES ('00000000000000000000000000000001','pergunta','resposta','[]',10,'test',false,CURRENT_TIMESTAMP)"
            )
        )
    command.upgrade(config, "head")
    with engine.connect() as db:
        assert db.execute(text("SELECT owner_id, mode, question FROM interactions")).one() == (
            "local",
            "direct",
            "pergunta",
        )
    inspector = inspect(engine)
    for name, table in Base.metadata.tables.items():
        assert {col["name"] for col in inspector.get_columns(name)} == set(table.columns.keys())
    command.check(config)
    command.downgrade(config, "ace48b94f7c9")
    with engine.connect() as db:
        assert db.execute(text("SELECT question FROM interactions")).scalar_one() == "pergunta"
    engine.dispose()
