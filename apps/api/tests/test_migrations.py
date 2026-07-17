from pathlib import Path
from sqlite3 import connect

from alembic import command
from alembic.config import Config


def test_migration_builds_sprint_two_schema(tmp_path: Path, monkeypatch: object) -> None:
    database_path = tmp_path / "migration.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)  # type: ignore[attr-defined]
    configuration = Config("alembic.ini")

    command.upgrade(configuration, "head")

    with connect(database_path) as connection:
        tables = {
            row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
        assert {
            "companies",
            "contacts",
            "opportunities",
            "tasks",
        }.issubset(tables)
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0002_core_business_entities",
        )
        task_columns = {row[1]: row[3] for row in connection.execute("PRAGMA table_info(tasks)").fetchall()}
        assert task_columns["organisation_id"] == 1
        assert task_columns["title"] == 1
        assert task_columns["created_by_user_id"] == 1

    command.downgrade(configuration, "0001_initial_schema")
    with connect(database_path) as connection:
        tables_after_downgrade = {
            row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
    assert not {"companies", "contacts", "opportunities", "tasks"} & tables_after_downgrade
