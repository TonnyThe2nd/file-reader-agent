from io import StringIO
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alembic import command
from alembic.config import Config
from app.core.config import settings

settings.database_url = 'postgresql://localhost/llmops'
root = Path(__file__).resolve().parents[1]
for revision, name in [('head', 'migrate_fresh.sql'), ('ace48b94f7c9:head', 'migrate_existing.sql'), ('b72e9c41a603:head', 'migrate_chat.sql')]:
    output = StringIO()
    config = Config(str(root / 'alembic.ini'), output_buffer=output)
    command.upgrade(config, revision, sql=True)
    (root / 'db' / name).write_text(output.getvalue(), encoding='utf-8')
    print(name)
