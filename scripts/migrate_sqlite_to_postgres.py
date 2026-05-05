from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import db  # noqa: E402


TABLE_MIGRATION_ORDER = [
    "companies",
    "branches",
    "roles",
    "permissions",
    "users",
    "user_roles",
    "user_companies",
    "user_branches",
    "role_permissions",
    "tasks",
    "meeting_notes",
    "meeting_templates",
    "documents",
    "recurring_documents",
    "suppliers",
    "supplier_interactions",
    "events",
    "record_user_shares",
    "record_role_shares",
    "attachments",
    "task_change_requests",
    "document_change_requests",
    "audit_logs",
    "sessions",
    "user_notification_settings",
    "file_upload_settings",
    "user_theme_settings",
]

REVERSE_TABLE_MIGRATION_ORDER = list(reversed(TABLE_MIGRATION_ORDER))


@dataclass(frozen=True)
class MigrationContext:
    sqlite_path: Path
    database_url: str
    execute: bool
    print_schema: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pelixi SQLite verisini PostgreSQL'e tasima iskeleti",
    )
    parser.add_argument(
        "--sqlite-path",
        default=str(db.DB_PATH),
        help="Kaynak SQLite dosya yolu. Varsayilan: aktif Pelixi DB yolu",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", ""),
        help="Hedef PostgreSQL baglanti adresi. Varsayilan: DATABASE_URL env",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Dry-run yerine gercek baglanti ve tasima adimlarini calistir",
    )
    parser.add_argument(
        "--print-schema",
        action="store_true",
        help="Olusturulacak PostgreSQL schema onizlemesini yazdir",
    )
    return parser.parse_args()


def build_context(args: argparse.Namespace) -> MigrationContext:
    sqlite_path = Path(args.sqlite_path).expanduser().resolve()
    database_url = (args.database_url or "").strip()
    return MigrationContext(
        sqlite_path=sqlite_path,
        database_url=database_url,
        execute=bool(args.execute),
        print_schema=bool(args.print_schema),
    )


def connect_sqlite(sqlite_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(sqlite_path)
    connection.row_factory = sqlite3.Row
    return connection


def connect_postgres(database_url: str):
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "PostgreSQL baglantisi icin 'psycopg' gerekli. "
            "Hazir oldugumuzda requirements ve kurulum adimini ekleyecegiz."
        ) from exc
    return psycopg.connect(database_url)


def validate_context(context: MigrationContext) -> None:
    if not context.sqlite_path.exists():
        raise FileNotFoundError(f"SQLite dosyasi bulunamadi: {context.sqlite_path}")
    if not context.database_url:
        raise ValueError("DATABASE_URL bos. PostgreSQL hedef adresi tanimli degil.")


def fetch_sqlite_count(connection: sqlite3.Connection, table_name: str) -> int:
    row = connection.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
    return int(row["count"]) if row else 0


def fetch_postgres_count(connection, table_name: str) -> int:
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        row = cursor.fetchone()
    return int(row[0]) if row else 0


def list_sqlite_columns(connection: sqlite3.Connection, table_name: str) -> list[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [str(row["name"]) for row in rows]


def list_sqlite_column_rows(connection: sqlite3.Connection, table_name: str) -> list[sqlite3.Row]:
    return connection.execute(f"PRAGMA table_info({table_name})").fetchall()


def list_postgres_columns(connection, table_name: str) -> list[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
            ORDER BY ordinal_position
            """,
            (table_name,),
        )
        return [str(row[0]) for row in cursor.fetchall()]


def print_plan(context: MigrationContext) -> None:
    print("Pelixi SQLite -> PostgreSQL migration plan")
    print("-" * 52)
    print(f"SQLite kaynak : {context.sqlite_path}")
    print(f"PostgreSQL hedef: {context.database_url or '[bos]'}")
    print(f"Calisma modu   : {'EXECUTE' if context.execute else 'DRY-RUN'}")
    print(f"Schema onizleme: {'ACIK' if context.print_schema else 'KAPALI'}")
    print()
    print("Tablo sirasi:")
    for index, table_name in enumerate(TABLE_MIGRATION_ORDER, start=1):
        print(f"{index:02d}. {table_name}")
    print()


def inspect_sqlite_source(context: MigrationContext) -> None:
    print("Kaynak SQLite kontrolu")
    print("-" * 52)
    with connect_sqlite(context.sqlite_path) as sqlite_connection:
        for table_name in TABLE_MIGRATION_ORDER:
            columns = list_sqlite_columns(sqlite_connection, table_name)
            count = fetch_sqlite_count(sqlite_connection, table_name)
            print(
                f"{table_name:<28} kayit={count:<6} kolon={len(columns):<3} "
                f"ornek={', '.join(columns[:5])}"
            )
    print()


def _normalize_schema_statement(statement: str) -> str:
    return "\n".join(line.rstrip() for line in statement.strip().splitlines())


def _convert_sqlite_schema_to_postgres(statement: str) -> str:
    postgres_sql = _normalize_schema_statement(statement)
    postgres_sql = postgres_sql.replace(
        "INTEGER PRIMARY KEY AUTOINCREMENT",
        "INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY",
    )
    postgres_sql = postgres_sql.replace(
        "id INTEGER PRIMARY KEY CHECK (id = 1)",
        "id INTEGER PRIMARY KEY CHECK (id = 1)",
    )
    postgres_sql = re.sub(
        r"\bcreated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP\b",
        "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
        postgres_sql,
    )
    postgres_sql = re.sub(
        r"\bupdated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP\b",
        "updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
        postgres_sql,
    )
    postgres_sql = re.sub(
        r"\bresolved_at TEXT\b",
        "resolved_at TIMESTAMP",
        postgres_sql,
    )
    postgres_sql = re.sub(
        r"\bsubmitted_at TEXT\b",
        "submitted_at TIMESTAMP",
        postgres_sql,
    )
    postgres_sql = re.sub(
        r"\bcompleted_at TEXT\b",
        "completed_at TIMESTAMP",
        postgres_sql,
    )
    postgres_sql = re.sub(
        r"\blast_completed_at TEXT\b",
        "last_completed_at TIMESTAMP",
        postgres_sql,
    )
    return postgres_sql


def get_postgres_schema_statements() -> list[str]:
    statements: list[str] = []
    for statement in db.SCHEMA_STATEMENTS:
        statements.append(_convert_sqlite_schema_to_postgres(statement))
    return statements


def print_postgres_schema_preview() -> None:
    print("PostgreSQL schema onizlemesi")
    print("-" * 52)
    for index, statement in enumerate(get_postgres_schema_statements(), start=1):
        print(f"[{index:02d}]")
        print(statement)
        print()


def create_postgres_schema(postgres_connection) -> None:
    schema_statements = get_postgres_schema_statements()
    with postgres_connection.cursor() as cursor:
        for statement in schema_statements:
            cursor.execute(statement)
    postgres_connection.commit()


def ensure_empty_postgres_tables(postgres_connection) -> None:
    non_empty_tables: list[tuple[str, int]] = []
    for table_name in TABLE_MIGRATION_ORDER:
        count = fetch_postgres_count(postgres_connection, table_name)
        if count > 0:
            non_empty_tables.append((table_name, count))
    if not non_empty_tables:
        return

    detail = ", ".join(f"{table}={count}" for table, count in non_empty_tables)
    raise RuntimeError(
        "Hedef PostgreSQL tablolarinda mevcut veri bulundu. "
        f"Ilk migration guvenligi icin hedefin bos olmasi gerekiyor: {detail}"
    )


def fetch_sqlite_rows(connection: sqlite3.Connection, table_name: str, columns: list[str]) -> list[tuple]:
    column_sql = ", ".join(columns)
    rows = connection.execute(f"SELECT {column_sql} FROM {table_name} ORDER BY rowid ASC").fetchall()
    return [tuple(row[column] for column in columns) for row in rows]


def build_postgres_insert_sql(table_name: str, columns: list[str]) -> str:
    column_sql = ", ".join(columns)
    placeholders = ", ".join("%s" for _ in columns)
    return f"INSERT INTO {table_name} ({column_sql}) VALUES ({placeholders})"


def _map_sqlite_type_to_postgres(sqlite_type: str) -> str:
    normalized = (sqlite_type or "").strip().upper()
    if "INT" in normalized:
        return "INTEGER"
    if "CHAR" in normalized or "CLOB" in normalized or "TEXT" in normalized:
        return "TEXT"
    if "BLOB" in normalized:
        return "BYTEA"
    if "REAL" in normalized or "FLOA" in normalized or "DOUB" in normalized:
        return "DOUBLE PRECISION"
    if "NUM" in normalized or "DEC" in normalized:
        return "NUMERIC"
    return "TEXT"


def _build_postgres_column_definition(column_row: sqlite3.Row) -> str:
    column_name = str(column_row["name"])
    column_type = _map_sqlite_type_to_postgres(str(column_row["type"]))
    not_null = " NOT NULL" if int(column_row["notnull"]) else ""
    default_value = column_row["dflt_value"]
    default_sql = f" DEFAULT {default_value}" if default_value is not None else ""
    return f"{column_name} {column_type}{not_null}{default_sql}"


def ensure_postgres_columns(postgres_connection, sqlite_connection: sqlite3.Connection, table_name: str) -> None:
    source_columns = list_sqlite_column_rows(sqlite_connection, table_name)
    target_columns = set(list_postgres_columns(postgres_connection, table_name))
    missing_columns = [row for row in source_columns if str(row["name"]) not in target_columns]
    if not missing_columns:
        return

    with postgres_connection.cursor() as cursor:
        for column_row in missing_columns:
            column_sql = _build_postgres_column_definition(column_row)
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")
    postgres_connection.commit()


def reset_postgres_identity(postgres_connection, table_name: str) -> None:
    with postgres_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
              AND is_identity = 'YES'
            ORDER BY ordinal_position
            LIMIT 1
            """,
            (table_name,),
        )
        row = cursor.fetchone()
        if not row:
            return
        identity_column = str(row[0])
        cursor.execute(
            f"""
            SELECT setval(
                pg_get_serial_sequence(%s, %s),
                COALESCE((SELECT MAX({identity_column}) FROM {table_name}), 1),
                true
            )
            """,
            (table_name, identity_column),
        )


def migrate_table(sqlite_connection: sqlite3.Connection, postgres_connection, table_name: str) -> None:
    ensure_postgres_columns(postgres_connection, sqlite_connection, table_name)
    columns = list_sqlite_columns(sqlite_connection, table_name)
    rows = fetch_sqlite_rows(sqlite_connection, table_name, columns)
    if not rows:
        print(f"{table_name:<28} kayit yok, atlandi")
        return

    insert_sql = build_postgres_insert_sql(table_name, columns)
    with postgres_connection.cursor() as cursor:
        cursor.executemany(insert_sql, rows)
    reset_postgres_identity(postgres_connection, table_name)
    postgres_connection.commit()
    print(f"{table_name:<28} tasindi: {len(rows)} kayit")


def validate_postgres_counts(sqlite_connection: sqlite3.Connection, postgres_connection) -> None:
    print()
    print("Kaynak / hedef sayi dogrulamasi")
    print("-" * 52)
    mismatches: list[str] = []
    for table_name in TABLE_MIGRATION_ORDER:
        sqlite_count = fetch_sqlite_count(sqlite_connection, table_name)
        postgres_count = fetch_postgres_count(postgres_connection, table_name)
        print(f"{table_name:<28} sqlite={sqlite_count:<6} postgres={postgres_count:<6}")
        if sqlite_count != postgres_count:
            mismatches.append(
                f"{table_name}: sqlite={sqlite_count}, postgres={postgres_count}"
            )
    if mismatches:
        raise RuntimeError(
            "Kayit sayisi dogrulamasi basarisiz: " + "; ".join(mismatches)
        )


def run_execute_mode(context: MigrationContext) -> None:
    validate_context(context)
    with connect_sqlite(context.sqlite_path) as sqlite_connection:
        with connect_postgres(context.database_url) as postgres_connection:
            create_postgres_schema(postgres_connection)
            ensure_empty_postgres_tables(postgres_connection)
            for table_name in TABLE_MIGRATION_ORDER:
                migrate_table(sqlite_connection, postgres_connection, table_name)
            validate_postgres_counts(sqlite_connection, postgres_connection)


def main() -> int:
    args = parse_args()
    context = build_context(args)
    print_plan(context)
    inspect_sqlite_source(context)
    if context.print_schema:
        print_postgres_schema_preview()

    if not context.execute:
        print("Dry-run tamamlandi. Hicbir hedef veritabani yazimi yapilmadi.")
        return 0

    try:
        run_execute_mode(context)
    except Exception as exc:  # pragma: no cover - runtime feedback path
        print()
        print(f"HATA: {exc}")
        return 1

    print()
    print("Migration tamamlandi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
