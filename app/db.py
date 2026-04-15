from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = Path(os.getenv("LOCALAPPDATA", str(BASE_DIR))) / "MyNotes"
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "my_notes.db"
BACKUP_DIR = APP_DIR / "backups"


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        responsible_person TEXT,
        description TEXT,
        category TEXT NOT NULL,
        priority TEXT NOT NULL,
        status TEXT NOT NULL,
        due_date TEXT,
        completed_at TEXT,
        related_type TEXT,
        related_id INTEGER,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS meeting_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        meeting_type TEXT,
        meeting_date TEXT NOT NULL,
        participants TEXT,
        agenda TEXT,
        notes TEXT,
        decisions TEXT,
        follow_up_items TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS meeting_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL UNIQUE,
        sort_order INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        institution TEXT,
        document_type TEXT,
        description TEXT,
        status TEXT NOT NULL,
        due_date TEXT,
        submitted_at TEXT,
        responsible_person TEXT,
        file_path TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS recurring_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        category TEXT,
        frequency TEXT NOT NULL,
        custom_interval_days INTEGER,
        last_completed_at TEXT,
        next_due_date TEXT NOT NULL,
        reminder_days_before INTEGER NOT NULL DEFAULT 7,
        responsible_person TEXT,
        notes TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT NOT NULL,
        contact_name TEXT,
        phone TEXT,
        email TEXT,
        service_type TEXT,
        price_notes TEXT,
        notes TEXT,
        last_contact_at TEXT,
        next_contact_at TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS supplier_interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id INTEGER NOT NULL,
        interaction_date TEXT NOT NULL,
        subject TEXT,
        notes TEXT,
        next_action_date TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (supplier_id) REFERENCES suppliers (id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        event_date TEXT NOT NULL,
        level TEXT NOT NULL,
        notes TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
]


DEFAULT_MEETING_TEMPLATES = [
    "Kurucu ekip toplantısı",
    "Haftalık öğretmen toplantısı",
    "İdari ekip toplantısı",
]


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    _create_daily_backup()
    with get_connection() as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        _ensure_column(connection, "tasks", "completed_at", "TEXT")
        _ensure_column(connection, "tasks", "responsible_person", "TEXT")
        if _is_empty(connection, "meeting_templates"):
            for index, title in enumerate(DEFAULT_MEETING_TEMPLATES, start=1):
                connection.execute(
                    "INSERT INTO meeting_templates (title, sort_order) VALUES (?, ?)",
                    (title, index),
                )
        _repair_text_data(connection)
        connection.commit()


def reset_database() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    init_db()


def _create_daily_backup() -> None:
    if not DB_PATH.exists():
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d")
    backup_path = BACKUP_DIR / f"my_notes_{stamp}.db"
    if not backup_path.exists():
        shutil.copy2(DB_PATH, backup_path)


def _repair_text_data(connection: sqlite3.Connection) -> None:
    tables = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    for table_row in tables:
        table_name = table_row["name"]
        columns = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        column_names = [column["name"] for column in columns]
        text_columns = [column["name"] for column in columns if column["type"].upper() == "TEXT"]
        if "id" not in column_names or not text_columns:
            continue
        rows = connection.execute(
            f"SELECT id, {', '.join(text_columns)} FROM {table_name}"
        ).fetchall()
        for row in rows:
            changed: dict[str, str] = {}
            for column_name in text_columns:
                original = row[column_name]
                repaired = _repair_mojibake(original)
                if repaired != original:
                    changed[column_name] = repaired
            if changed:
                assignments = ", ".join(f"{column} = ?" for column in changed)
                params = tuple(changed.values()) + (row["id"],)
                connection.execute(
                    f"UPDATE {table_name} SET {assignments} WHERE id = ?",
                    params,
                )


def _repair_mojibake(value: str | None) -> str | None:
    if not value or not isinstance(value, str):
        return value
    if not any(char in value for char in ("Ã", "Ä", "Å", "Â")):
        return value
    try:
        repaired = value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value
    return repaired


def _is_empty(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
    return bool(row["count"] == 0)


def _ensure_column(
    connection: sqlite3.Connection, table_name: str, column_name: str, column_definition: str
) -> None:
    columns = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    if any(column["name"] == column_name for column in columns):
        return
    connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


def fetch_all(query: str, params: tuple = ()) -> list[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute(query, params).fetchall()


def fetch_one(query: str, params: tuple = ()) -> sqlite3.Row | None:
    with get_connection() as connection:
        return connection.execute(query, params).fetchone()


def execute(query: str, params: tuple = ()) -> None:
    with get_connection() as connection:
        connection.execute(query, params)
        connection.commit()


def execute_insert(query: str, params: tuple = ()) -> int:
    with get_connection() as connection:
        cursor = connection.execute(query, params)
        connection.commit()
        return int(cursor.lastrowid)
