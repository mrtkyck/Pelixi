from __future__ import annotations

import os
import hashlib
import hmac
import secrets
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_APP_DIR = Path(os.getenv("LOCALAPPDATA", str(BASE_DIR))) / "MyNotes"
FALLBACK_APP_DIR = BASE_DIR / ".mynotes-local"
DB_BACKEND = (os.getenv("PELIXI_DB_BACKEND") or os.getenv("MYNOTES_DB_BACKEND") or "sqlite").strip().lower()
DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()


def _is_sqlite_path_writable(db_path: Path) -> bool:
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with open(db_path, "a+b"):
            pass
        return True
    except OSError:
        return False


def _resolve_app_dir() -> Path:
    preferred_app_dir = Path(os.getenv("MYNOTES_APP_DIR") or DEFAULT_APP_DIR)
    candidates = [preferred_app_dir, FALLBACK_APP_DIR]
    for candidate in candidates:
        db_path = candidate / "data" / "my_notes.db"
        if _is_sqlite_path_writable(db_path):
            return candidate
    return BASE_DIR


APP_DIR = _resolve_app_dir()
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "my_notes.db"
BACKUP_DIR = APP_DIR / "backups"


def get_database_backend() -> str:
    return DB_BACKEND


def is_sqlite_backend() -> bool:
    return get_database_backend() == "sqlite"


def get_database_target() -> str:
    if is_sqlite_backend():
        return str(DB_PATH)
    return DATABASE_URL or "DATABASE_URL tanimli degil"


def _ensure_sqlite_backend(feature_name: str) -> None:
    if is_sqlite_backend():
        return
    raise NotImplementedError(
        f"{feature_name} henuz '{get_database_backend()}' icin hazir degil. "
        "PostgreSQL gecisinde bu katman bir sonraki adimda tamamlanacak."
    )


def _sql_string_agg(expression: str, delimiter: str = ",", order_by: str = "") -> str:
    if is_sqlite_backend():
        return f"GROUP_CONCAT({expression}, '{delimiter}')"
    ordered = f" ORDER BY {order_by}" if order_by else ""
    return f"string_agg({expression}, '{delimiter}'{ordered})"


def _sql_current_session_cutoff() -> str:
    if is_sqlite_backend():
        return "datetime('now', 'localtime')"
    return "CURRENT_TIMESTAMP"


def _sql_date_value(value_placeholder: str = "?") -> str:
    if is_sqlite_backend():
        return f"date({value_placeholder})"
    return f"CAST({value_placeholder} AS DATE)"


def _sql_date_column(column_name: str) -> str:
    if is_sqlite_backend():
        return f"date({column_name})"
    return f"CAST({column_name} AS DATE)"


def _sql_placeholders(count: int) -> str:
    return ",".join("?" for _ in range(max(0, count)))


def _sql_insert_ignore(table_name: str, columns: tuple[str, ...]) -> str:
    column_sql = ", ".join(columns)
    placeholders = _sql_placeholders(len(columns))
    if is_sqlite_backend():
        return f"INSERT OR IGNORE INTO {table_name} ({column_sql}) VALUES ({placeholders})"
    return (
        f"INSERT INTO {table_name} ({column_sql}) VALUES ({placeholders}) "
        "ON CONFLICT DO NOTHING"
    )


def _get_table_columns(connection: sqlite3.Connection, table_name: str) -> list[sqlite3.Row]:
    _ensure_sqlite_backend("Tablo kolon kontrolu")
    return connection.execute(f"PRAGMA table_info({table_name})").fetchall()


def _get_last_insert_id(cursor, feature_name: str = "Kayit ekleme") -> int:
    if is_sqlite_backend():
        return int(cursor.lastrowid)
    raise NotImplementedError(
        f"{feature_name} icin son eklenen kayit kimligi henuz '{get_database_backend()}' icin hazir degil."
    )


USER_DETAIL_SELECT = (
    "users.*, "
    "companies.name AS company_name, companies.code AS company_code, "
    "branches.name AS branch_name, branches.code AS branch_code, "
    f"(SELECT {_sql_string_agg('companies.name', ', ')} FROM user_companies "
    " INNER JOIN companies ON companies.id = user_companies.company_id "
    " WHERE user_companies.user_id = users.id) AS company_names, "
    f"(SELECT {_sql_string_agg('companies.code', ',')} FROM user_companies "
    " INNER JOIN companies ON companies.id = user_companies.company_id "
    " WHERE user_companies.user_id = users.id) AS company_codes, "
    f"(SELECT {_sql_string_agg('CAST(user_companies.company_id AS TEXT)', ',')} FROM user_companies "
    " WHERE user_companies.user_id = users.id) AS company_ids, "
    f"(SELECT {_sql_string_agg('branches.name', ', ')} FROM user_branches "
    " INNER JOIN branches ON branches.id = user_branches.branch_id "
    " WHERE user_branches.user_id = users.id) AS branch_names, "
    f"(SELECT {_sql_string_agg('branches.code', ',')} FROM user_branches "
    " INNER JOIN branches ON branches.id = user_branches.branch_id "
    " WHERE user_branches.user_id = users.id) AS branch_codes, "
    f"(SELECT {_sql_string_agg('CAST(user_branches.branch_id AS TEXT)', ',')} FROM user_branches "
    " WHERE user_branches.user_id = users.id) AS branch_ids, "
    f"(SELECT {_sql_string_agg('roles.code', ',')} FROM user_roles "
    " INNER JOIN roles ON roles.id = user_roles.role_id "
    " WHERE user_roles.user_id = users.id) AS role_codes "
)


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        code TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS branches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        code TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(company_id, code),
        FOREIGN KEY (company_id) REFERENCES companies (id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        full_name TEXT,
        email TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        description TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        module_name TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        role_id INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, role_id),
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (role_id) REFERENCES roles (id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_branches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        branch_id INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, branch_id),
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (branch_id) REFERENCES branches (id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        company_id INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, company_id),
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (company_id) REFERENCES companies (id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS role_permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role_id INTEGER NOT NULL,
        permission_id INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(role_id, permission_id),
        FOREIGN KEY (role_id) REFERENCES roles (id),
        FOREIGN KEY (permission_id) REFERENCES permissions (id)
    )
    """,
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
    CREATE TABLE IF NOT EXISTS meeting_agenda_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meeting_id INTEGER NOT NULL,
        body TEXT NOT NULL,
        author_user_id INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (meeting_id) REFERENCES meeting_notes (id) ON DELETE CASCADE,
        FOREIGN KEY (author_user_id) REFERENCES users (id)
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
    """
    CREATE TABLE IF NOT EXISTS attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_name TEXT NOT NULL,
        record_id INTEGER NOT NULL,
        original_name TEXT NOT NULL,
        stored_name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        mime_type TEXT,
        file_size INTEGER,
        uploaded_by INTEGER,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (uploaded_by) REFERENCES users (id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS record_user_shares (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_name TEXT NOT NULL,
        record_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(module_name, record_id, user_id),
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS record_role_shares (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_name TEXT NOT NULL,
        record_id INTEGER NOT NULL,
        role_id INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(module_name, record_id, role_id),
        FOREIGN KEY (role_id) REFERENCES roles (id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS task_change_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL,
        owner_user_id INTEGER NOT NULL,
        requester_user_id INTEGER NOT NULL,
        request_type TEXT NOT NULL,
        payload TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        resolved_at TEXT,
        resolved_by INTEGER,
        FOREIGN KEY (task_id) REFERENCES tasks (id),
        FOREIGN KEY (owner_user_id) REFERENCES users (id),
        FOREIGN KEY (requester_user_id) REFERENCES users (id),
        FOREIGN KEY (resolved_by) REFERENCES users (id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS document_change_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL,
        document_kind TEXT NOT NULL,
        owner_user_id INTEGER NOT NULL,
        requester_user_id INTEGER NOT NULL,
        request_type TEXT NOT NULL,
        payload TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        resolved_at TEXT,
        resolved_by INTEGER,
        owner_hidden_at TEXT,
        requester_hidden_at TEXT,
        FOREIGN KEY (owner_user_id) REFERENCES users (id),
        FOREIGN KEY (requester_user_id) REFERENCES users (id),
        FOREIGN KEY (resolved_by) REFERENCES users (id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT NOT NULL,
        module_name TEXT NOT NULL,
        record_id INTEGER,
        details TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT NOT NULL UNIQUE,
        user_id INTEGER NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_notification_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        badge_pending_requests INTEGER NOT NULL DEFAULT 1,
        approval_items INTEGER NOT NULL DEFAULT 1,
        outgoing_items INTEGER NOT NULL DEFAULT 1,
        task_alerts INTEGER NOT NULL DEFAULT 1,
        document_alerts INTEGER NOT NULL DEFAULT 1,
        event_reminders INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS file_upload_settings (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        allowed_extensions TEXT NOT NULL,
        max_file_size_mb INTEGER NOT NULL DEFAULT 10,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_theme_settings (
        user_id INTEGER PRIMARY KEY,
        theme TEXT NOT NULL DEFAULT 'light',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """,
]


DEFAULT_MEETING_TEMPLATES = [
    "Kurucu ekip toplantısı",
    "Haftalık öğretmen toplantısı",
    "İdari ekip toplantısı",
]

DEFAULT_ROLES = [
    ("admin", "Admin", "Sistemin tüm ayarlarını ve kullanıcılarını yönetir."),
    ("kurucu", "Kurucu", "Kurumsal modüllerin büyük bölümünü görür ve yönetir."),
    ("yonetici", "Yönetici", "Operasyonel kayıtları yönetir."),
    ("ogretmen", "Öğretmen", "Kendine ait ve paylaşılan kayıtları görür."),
    ("sekreterya", "Sekreterya", "Evrak ve tedarikçi süreçlerini yönetir."),
]

SYSTEM_ROLE_CODES = {code for code, _, _ in DEFAULT_ROLES}

DEFAULT_PERMISSIONS = [
    ("tasks.view", "Görevleri Gör", "tasks"),
    ("tasks.create", "Görev Oluştur", "tasks"),
    ("tasks.edit", "Görev Düzenle", "tasks"),
    ("tasks.delete", "Görev Sil", "tasks"),
    ("meetings.view", "Toplantıları Gör", "meetings"),
    ("meetings.create", "Toplantı Oluştur", "meetings"),
    ("meetings.edit", "Toplantı Düzenle", "meetings"),
    ("meetings.delete", "Toplantı Sil", "meetings"),
    ("documents.view", "Evrakları Gör", "documents"),
    ("documents.create", "Evrak Oluştur", "documents"),
    ("documents.edit", "Evrak Düzenle", "documents"),
    ("documents.delete", "Evrak Sil", "documents"),
    ("events.view", "Etkinlikleri Gör", "events"),
    ("events.create", "Etkinlik Oluştur", "events"),
    ("events.edit", "Etkinlik Düzenle", "events"),
    ("events.delete", "Etkinlik Sil", "events"),
    ("suppliers.view", "Tedarikçileri Gör", "suppliers"),
    ("suppliers.create", "Tedarikçi Oluştur", "suppliers"),
    ("suppliers.edit", "Tedarikçi Düzenle", "suppliers"),
    ("suppliers.delete", "Tedarikçi Sil", "suppliers"),
    ("attachments.upload", "Dosya Yükle", "attachments"),
    ("attachments.delete", "Dosya Sil", "attachments"),
    ("users.manage", "Kullanıcıları Yönet", "users"),
    ("roles.manage", "Rolleri Yönet", "roles"),
]

ROLE_PERMISSION_MAP = {
    "admin": [code for code, _, _ in DEFAULT_PERMISSIONS],
    "kurucu": [
        "tasks.view", "tasks.create", "tasks.edit",
        "meetings.view", "meetings.create", "meetings.edit",
        "documents.view", "documents.create", "documents.edit",
        "events.view", "events.create", "events.edit",
        "suppliers.view", "suppliers.create", "suppliers.edit",
        "attachments.upload",
    ],
    "yonetici": [
        "tasks.view", "tasks.create", "tasks.edit",
        "meetings.view", "meetings.create", "meetings.edit",
        "documents.view", "documents.create", "documents.edit",
        "events.view", "events.create", "events.edit",
        "suppliers.view",
        "attachments.upload",
    ],
    "ogretmen": [
        "tasks.view",
        "meetings.view",
        "documents.view",
        "events.view",
    ],
    "sekreterya": [
        "tasks.view", "tasks.create", "tasks.edit",
        "meetings.view",
        "documents.view", "documents.create", "documents.edit",
        "suppliers.view", "suppliers.create", "suppliers.edit",
        "attachments.upload",
    ],
}

OWNED_TABLES = (
    "tasks",
    "meeting_notes",
    "documents",
    "recurring_documents",
    "suppliers",
    "supplier_interactions",
    "events",
)

PASSWORD_ITERATIONS = 120_000
SESSION_DURATION_DAYS = 30
DEFAULT_FILE_SETTINGS = {
    "allowed_extensions": ".pdf, .doc, .docx, .xls, .xlsx, .png, .jpg, .jpeg, .zip",
    "max_file_size_mb": 10,
}


def get_connection() -> sqlite3.Connection:
    _ensure_sqlite_backend("Veritabani baglantisi")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    _ensure_sqlite_backend("Veritabani kurulumu")
    _create_daily_backup()
    with get_connection() as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        _ensure_column(connection, "users", "phone", "TEXT")
        _ensure_column(connection, "users", "company_id", "INTEGER")
        _ensure_column(connection, "users", "branch_id", "INTEGER")
        _ensure_column(connection, "tasks", "completed_at", "TEXT")
        _ensure_column(connection, "tasks", "responsible_person", "TEXT")
        _ensure_column(connection, "events", "end_date", "TEXT")
        _ensure_column(connection, "events", "time_range", "TEXT")
        _ensure_column(connection, "task_change_requests", "owner_hidden_at", "TEXT")
        _ensure_column(connection, "task_change_requests", "requester_hidden_at", "TEXT")
        _ensure_column(connection, "document_change_requests", "owner_hidden_at", "TEXT")
        _ensure_column(connection, "document_change_requests", "requester_hidden_at", "TEXT")
        _ensure_owned_record_columns(connection)
        _ensure_meeting_agenda_table(connection)
        _backfill_meeting_owners_if_needed(connection)
        _migrate_meeting_agenda_to_items(connection)
        _sync_user_company_links(connection)
        if _is_empty(connection, "meeting_templates"):
            for index, title in enumerate(DEFAULT_MEETING_TEMPLATES, start=1):
                connection.execute(
                    "INSERT INTO meeting_templates (title, sort_order) VALUES (?, ?)",
                    (title, index),
                )
        _seed_roles_and_permissions(connection)
        _repair_text_data(connection)
        connection.commit()


def reset_database() -> None:
    _ensure_sqlite_backend("Veritabani sifirlama")
    if DB_PATH.exists():
        DB_PATH.unlink()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    init_db()


def _create_daily_backup() -> None:
    _ensure_sqlite_backend("Gunluk yedekleme")
    if not DB_PATH.exists():
        return
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d")
        backup_path = BACKUP_DIR / f"my_notes_{stamp}.db"
        if not backup_path.exists():
            _backup_database_to(backup_path)
    except (PermissionError, OSError):
        # Yedek alınamasa bile uygulama açılışı durmasın.
        return


def _backup_database_to(target_path: Path) -> Path:
    _ensure_sqlite_backend("Yedekleme")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        target_path.unlink()
    with sqlite3.connect(DB_PATH) as source_connection, sqlite3.connect(target_path) as backup_connection:
        source_connection.backup(backup_connection)
    return target_path


def create_backup_now() -> Path:
    _ensure_sqlite_backend("Manuel yedekleme")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = BACKUP_DIR / f"my_notes_manual_{stamp}.db"
    return _backup_database_to(backup_path)


def _sync_user_company_links(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        "SELECT id, company_id FROM users WHERE company_id IS NOT NULL"
    ).fetchall()
    for row in rows:
        connection.execute(
            _sql_insert_ignore("user_companies", ("user_id", "company_id")),
            (row["id"], row["company_id"]),
        )


def list_backups() -> list[dict]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    items: list[dict] = []
    for path in sorted(BACKUP_DIR.glob("*.db"), key=lambda item: item.stat().st_mtime, reverse=True):
        stat = path.stat()
        items.append(
            {
                "name": path.name,
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "is_manual": 1 if "_manual_" in path.name else 0,
            }
        )
    return items


def get_backup_path(file_name: str) -> Path | None:
    cleaned = Path(file_name).name
    if not cleaned.endswith(".db"):
        return None
    path = BACKUP_DIR / cleaned
    if not path.exists() or path.parent.resolve() != BACKUP_DIR.resolve():
        return None
    return path


def add_audit_log(
    user_id: int | None,
    action: str,
    module_name: str,
    record_id: int | None = None,
    details: str = "",
) -> int:
    return execute_insert(
        "INSERT INTO audit_logs (user_id, action, module_name, record_id, details) VALUES (?, ?, ?, ?, ?)",
        (
            user_id,
            action.strip(),
            module_name.strip(),
            record_id,
            details.strip(),
        ),
    )


def list_audit_logs(
    limit: int = 150,
    search: str = "",
    date_from: str = "",
    date_to: str = "",
    module_name: str = "",
    actor_name: str = "",
    action: str = "",
) -> list[sqlite3.Row]:
    safe_limit = max(1, min(int(limit), 5000))
    filters: list[str] = []
    params: list = []
    if search.strip():
        filters.append(
            "("
            "LOWER(COALESCE(audit_logs.action, '')) LIKE ? OR "
            "LOWER(COALESCE(audit_logs.module_name, '')) LIKE ? OR "
            "LOWER(COALESCE(audit_logs.details, '')) LIKE ? OR "
            "LOWER(COALESCE(users.full_name, users.username, '')) LIKE ?"
            ")"
        )
        like_value = f"%{search.strip().lower()}%"
        params.extend([like_value, like_value, like_value, like_value])
    if date_from.strip():
        filters.append(f"{_sql_date_column('audit_logs.created_at')} >= {_sql_date_value()}")
        params.append(date_from.strip())
    if date_to.strip():
        filters.append(f"{_sql_date_column('audit_logs.created_at')} <= {_sql_date_value()}")
        params.append(date_to.strip())
    if module_name.strip():
        filters.append("audit_logs.module_name = ?")
        params.append(module_name.strip())
    if actor_name.strip():
        filters.append("COALESCE(NULLIF(users.full_name, ''), NULLIF(users.username, ''), 'Sistem') = ?")
        params.append(actor_name.strip())
    if action.strip():
        filters.append("audit_logs.action = ?")
        params.append(action.strip())
    where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""
    return fetch_all(
        "SELECT audit_logs.*, "
        "COALESCE(NULLIF(users.full_name, ''), NULLIF(users.username, ''), 'Sistem') AS actor_name "
        "FROM audit_logs "
        "LEFT JOIN users ON users.id = audit_logs.user_id "
        f"{where_sql} "
        "ORDER BY audit_logs.created_at DESC, audit_logs.id DESC "
        f"LIMIT {safe_limit}",
        tuple(params),
    )


def list_audit_modules() -> list[str]:
    rows = fetch_all(
        "SELECT DISTINCT module_name FROM audit_logs WHERE TRIM(COALESCE(module_name, '')) <> '' ORDER BY module_name ASC"
    )
    return [str(row["module_name"]) for row in rows]


def list_audit_users() -> list[str]:
    rows = fetch_all(
        "SELECT DISTINCT COALESCE(NULLIF(users.full_name, ''), NULLIF(users.username, ''), 'Sistem') AS actor_name "
        "FROM audit_logs "
        "LEFT JOIN users ON users.id = audit_logs.user_id "
        "ORDER BY actor_name ASC"
    )
    return [str(row["actor_name"]) for row in rows if row["actor_name"]]


def list_audit_actions() -> list[str]:
    rows = fetch_all(
        "SELECT DISTINCT action FROM audit_logs WHERE TRIM(COALESCE(action, '')) <> '' ORDER BY action ASC"
    )
    return [str(row["action"]) for row in rows]


def _repair_text_data(connection: sqlite3.Connection) -> None:
    tables = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    for table_row in tables:
        table_name = table_row["name"]
        columns = _get_table_columns(connection, table_name)
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


def _ensure_owned_record_columns(connection: sqlite3.Connection) -> None:
    for table_name in OWNED_TABLES:
        _ensure_column(connection, table_name, "owner_user_id", "INTEGER")
        _ensure_column(
            connection,
            table_name,
            "visibility_type",
            "TEXT NOT NULL DEFAULT 'private'",
        )
        _ensure_column(connection, table_name, "created_by", "INTEGER")
        _ensure_column(connection, table_name, "updated_by", "INTEGER")
        _ensure_column(connection, table_name, "is_archived", "INTEGER NOT NULL DEFAULT 0")


def _ensure_meeting_agenda_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS meeting_agenda_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER NOT NULL,
            body TEXT NOT NULL,
            author_user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (meeting_id) REFERENCES meeting_notes (id) ON DELETE CASCADE,
            FOREIGN KEY (author_user_id) REFERENCES users (id)
        )
        """
    )


def _backfill_meeting_owners_if_needed(connection: sqlite3.Connection) -> None:
    row = connection.execute("SELECT COUNT(*) AS c FROM meeting_notes WHERE owner_user_id IS NULL").fetchone()
    if not row or int(row["c"]) == 0:
        return
    first_user = connection.execute("SELECT id FROM users ORDER BY id ASC LIMIT 1").fetchone()
    uid = int(first_user["id"]) if first_user else 1
    connection.execute(
        "UPDATE meeting_notes SET owner_user_id = ?, visibility_type = COALESCE(NULLIF(TRIM(visibility_type), ''), 'private') "
        "WHERE owner_user_id IS NULL",
        (uid,),
    )


def _migrate_meeting_agenda_to_items(connection: sqlite3.Connection) -> None:
    meetings = connection.execute(
        "SELECT id, agenda, owner_user_id FROM meeting_notes WHERE TRIM(COALESCE(agenda, '')) != ''"
    ).fetchall()
    for m in meetings:
        mid = int(m["id"])
        existing = connection.execute(
            "SELECT COUNT(*) AS c FROM meeting_agenda_items WHERE meeting_id = ?",
            (mid,),
        ).fetchone()
        if existing and int(existing["c"]) > 0:
            continue
        owner = int(m["owner_user_id"] or 1)
        text = str(m["agenda"] or "")
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            connection.execute(
                "INSERT INTO meeting_agenda_items (meeting_id, body, author_user_id) VALUES (?, ?, ?)",
                (mid, stripped, owner),
            )
        connection.execute("UPDATE meeting_notes SET agenda = '' WHERE id = ?", (mid,))


def _seed_roles_and_permissions(connection: sqlite3.Connection) -> None:
    for code, name, description in DEFAULT_ROLES:
        connection.execute(
            _sql_insert_ignore("roles", ("code", "name", "description")),
            (code, name, description),
        )

    for code, name, module_name in DEFAULT_PERMISSIONS:
        connection.execute(
            _sql_insert_ignore("permissions", ("code", "name", "module_name")),
            (code, name, module_name),
        )

    role_rows = connection.execute("SELECT id, code FROM roles").fetchall()
    permission_rows = connection.execute("SELECT id, code FROM permissions").fetchall()
    role_ids = {row["code"]: row["id"] for row in role_rows}
    permission_ids = {row["code"]: row["id"] for row in permission_rows}

    for role_code, permission_codes in ROLE_PERMISSION_MAP.items():
        role_id = role_ids.get(role_code)
        if not role_id:
            continue
        for permission_code in permission_codes:
            permission_id = permission_ids.get(permission_code)
            if not permission_id:
                continue
            connection.execute(
                _sql_insert_ignore("role_permissions", ("role_id", "permission_id")),
                (role_id, permission_id),
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
    columns = _get_table_columns(connection, table_name)
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
        return _get_last_insert_id(cursor)


def count_users() -> int:
    row = fetch_one("SELECT COUNT(*) AS count FROM users")
    return int(row["count"]) if row else 0


def list_companies() -> list[sqlite3.Row]:
    return fetch_all(
        "SELECT companies.*, "
        "(SELECT COUNT(*) FROM branches WHERE branches.company_id = companies.id) AS branch_count, "
        "(SELECT COUNT(*) FROM users WHERE users.company_id = companies.id) AS user_count "
        "FROM companies "
        "ORDER BY companies.name ASC"
    )


def get_company_by_id(company_id: int) -> sqlite3.Row | None:
    return fetch_one("SELECT * FROM companies WHERE id = ?", (company_id,))


def get_company_by_name(name: str) -> sqlite3.Row | None:
    return fetch_one("SELECT * FROM companies WHERE lower(name) = lower(?)", (name.strip(),))


def create_company(name: str, code: str) -> int:
    return execute_insert(
        "INSERT INTO companies (name, code, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        (name.strip(), code.strip()),
    )


def update_company(company_id: int, name: str, code: str) -> None:
    execute(
        "UPDATE companies SET name = ?, code = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (name.strip(), code.strip(), company_id),
    )


def delete_company(company_id: int) -> None:
    execute("DELETE FROM companies WHERE id = ?", (company_id,))


def list_branches(company_id: int | None = None) -> list[sqlite3.Row]:
    if company_id:
        return fetch_all(
            "SELECT branches.*, companies.name AS company_name, companies.code AS company_code, "
            "(SELECT COUNT(*) FROM user_branches WHERE user_branches.branch_id = branches.id) AS user_count "
            "FROM branches "
            "INNER JOIN companies ON companies.id = branches.company_id "
            "WHERE branches.company_id = ? "
            "ORDER BY companies.name ASC, branches.name ASC",
            (company_id,),
        )
    return fetch_all(
        "SELECT branches.*, companies.name AS company_name, companies.code AS company_code, "
        "(SELECT COUNT(*) FROM user_branches WHERE user_branches.branch_id = branches.id) AS user_count "
        "FROM branches "
        "INNER JOIN companies ON companies.id = branches.company_id "
        "ORDER BY companies.name ASC, branches.name ASC"
    )


def get_branch_by_id(branch_id: int) -> sqlite3.Row | None:
    return fetch_one(
        "SELECT branches.*, companies.name AS company_name, companies.code AS company_code "
        "FROM branches INNER JOIN companies ON companies.id = branches.company_id "
        "WHERE branches.id = ?",
        (branch_id,),
    )


def create_branch(company_id: int, name: str, code: str) -> int:
    return execute_insert(
        "INSERT INTO branches (company_id, name, code, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        (company_id, name.strip(), code.strip()),
    )


def update_branch(branch_id: int, company_id: int, name: str, code: str) -> None:
    execute(
        "UPDATE branches SET company_id = ?, name = ?, code = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (company_id, name.strip(), code.strip(), branch_id),
    )


def delete_branch(branch_id: int) -> None:
    execute("DELETE FROM branches WHERE id = ?", (branch_id,))


def count_users_for_company(company_id: int) -> int:
    row = fetch_one("SELECT COUNT(*) AS count FROM user_companies WHERE company_id = ?", (company_id,))
    return int(row["count"]) if row else 0


def count_users_for_branch(branch_id: int) -> int:
    row = fetch_one("SELECT COUNT(*) AS count FROM user_branches WHERE branch_id = ?", (branch_id,))
    return int(row["count"]) if row else 0


USER_DETAIL_SQL = (
    "SELECT "
    + USER_DETAIL_SELECT
    + "FROM users "
      "LEFT JOIN companies ON companies.id = users.company_id "
      "LEFT JOIN branches ON branches.id = users.branch_id"
)


def get_user_by_username(username: str) -> sqlite3.Row | None:
    key = (username or "").strip()
    if not key:
        return None
    return fetch_one("SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (key,))


def get_user_by_id(user_id: int) -> sqlite3.Row | None:
    return fetch_one(
        USER_DETAIL_SQL + " WHERE users.id = ? GROUP BY users.id",
        (user_id,),
    )


def get_user_by_email(email: str) -> sqlite3.Row | None:
    return fetch_one("SELECT * FROM users WHERE email = ?", (email.strip(),))


def list_users() -> list[sqlite3.Row]:
    return fetch_all(
        USER_DETAIL_SQL + 
        " GROUP BY users.id ORDER BY users.full_name ASC, users.username ASC"
    )


def list_active_users() -> list[sqlite3.Row]:
    return fetch_all(
        USER_DETAIL_SQL + 
        " WHERE users.is_active = 1 GROUP BY users.id ORDER BY users.full_name ASC, users.username ASC"
    )


def list_roles() -> list[sqlite3.Row]:
    return fetch_all("SELECT * FROM roles ORDER BY name ASC")


def get_role_by_code(code: str) -> sqlite3.Row | None:
    return fetch_one("SELECT * FROM roles WHERE code = ?", (code.strip(),))


def create_role(code: str, name: str, description: str = "") -> int:
    return execute_insert(
        "INSERT INTO roles (code, name, description) VALUES (?, ?, ?)",
        (code.strip(), name.strip(), description.strip()),
    )


def update_role(code: str, name: str, description: str = "") -> None:
    execute(
        "UPDATE roles SET name = ?, description = ? WHERE code = ?",
        (name.strip(), description.strip(), code.strip()),
    )


def delete_role(code: str) -> None:
    with get_connection() as connection:
        role_row = connection.execute("SELECT id FROM roles WHERE code = ?", (code.strip(),)).fetchone()
        if not role_row:
            return
        role_id = role_row["id"]
        connection.execute("DELETE FROM role_permissions WHERE role_id = ?", (role_id,))
        connection.execute("DELETE FROM user_roles WHERE role_id = ?", (role_id,))
        connection.execute("DELETE FROM roles WHERE id = ?", (role_id,))
        connection.commit()


def count_users_for_role(code: str) -> int:
    row = fetch_one(
        "SELECT COUNT(*) AS count FROM user_roles "
        "INNER JOIN roles ON roles.id = user_roles.role_id "
        "WHERE roles.code = ?",
        (code.strip(),),
    )
    return int(row["count"]) if row else 0


def get_notification_settings(user_id: int) -> dict:
    row = fetch_one("SELECT * FROM user_notification_settings WHERE user_id = ?", (user_id,))
    defaults = {
        "badge_pending_requests": 1,
        "approval_items": 1,
        "outgoing_items": 1,
        "task_alerts": 1,
        "document_alerts": 1,
        "event_reminders": 1,
    }
    if not row:
        return defaults
    data = dict(row)
    for key, value in defaults.items():
        data[key] = int(data.get(key, value))
    return data


def save_notification_settings(user_id: int, settings: dict[str, int]) -> None:
    values = {
        "badge_pending_requests": 1 if settings.get("badge_pending_requests") else 0,
        "approval_items": 1 if settings.get("approval_items") else 0,
        "outgoing_items": 1 if settings.get("outgoing_items") else 0,
        "task_alerts": 1 if settings.get("task_alerts") else 0,
        "document_alerts": 1 if settings.get("document_alerts") else 0,
        "event_reminders": 1 if settings.get("event_reminders") else 0,
    }
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO user_notification_settings (
                user_id, badge_pending_requests, approval_items, outgoing_items,
                task_alerts, document_alerts, event_reminders, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                badge_pending_requests = excluded.badge_pending_requests,
                approval_items = excluded.approval_items,
                outgoing_items = excluded.outgoing_items,
                task_alerts = excluded.task_alerts,
                document_alerts = excluded.document_alerts,
                event_reminders = excluded.event_reminders,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                values["badge_pending_requests"],
                values["approval_items"],
                values["outgoing_items"],
                values["task_alerts"],
                values["document_alerts"],
                values["event_reminders"],
            ),
        )
        connection.commit()


def get_file_settings() -> dict:
    row = fetch_one("SELECT * FROM file_upload_settings WHERE id = 1")
    defaults = dict(DEFAULT_FILE_SETTINGS)
    if not row:
        return defaults
    data = dict(row)
    allowed_extensions = str(data.get("allowed_extensions") or defaults["allowed_extensions"]).strip()
    max_file_size_mb = data.get("max_file_size_mb", defaults["max_file_size_mb"])
    try:
        max_file_size_mb = max(1, int(max_file_size_mb))
    except (TypeError, ValueError):
        max_file_size_mb = int(defaults["max_file_size_mb"])
    return {
        "allowed_extensions": allowed_extensions,
        "max_file_size_mb": max_file_size_mb,
    }


def save_file_settings(allowed_extensions: str, max_file_size_mb: int) -> None:
    normalized_extensions = allowed_extensions.strip() or str(DEFAULT_FILE_SETTINGS["allowed_extensions"])
    safe_limit = max(1, int(max_file_size_mb))
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO file_upload_settings (
                id, allowed_extensions, max_file_size_mb, updated_at
            ) VALUES (1, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                allowed_extensions = excluded.allowed_extensions,
                max_file_size_mb = excluded.max_file_size_mb,
                updated_at = CURRENT_TIMESTAMP
            """,
            (normalized_extensions, safe_limit),
        )
        connection.commit()


def get_theme_settings(user_id: int) -> dict:
    row = fetch_one("SELECT * FROM user_theme_settings WHERE user_id = ?", (user_id,))
    if not row:
        return {"theme": "light"}
    return {"theme": str(row["theme"]) or "light"}


def save_theme_settings(user_id: int, theme: str) -> None:
    valid_themes = ["light", "dark"]
    theme = theme.strip().lower() if theme else "light"
    if theme not in valid_themes:
        theme = "light"
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO user_theme_settings (user_id, theme, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                theme = excluded.theme,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, theme),
        )
        connection.commit()


def list_permissions() -> list[sqlite3.Row]:
    return fetch_all("SELECT * FROM permissions ORDER BY module_name ASC, name ASC")


def create_user(
    username: str,
    password: str,
    full_name: str = "",
    email: str = "",
    phone: str = "",
    company_id: int | None = None,
    company_ids: list[int] | None = None,
    branch_id: int | None = None,
    branch_ids: list[int] | None = None,
    role_codes: list[str] | None = None,
) -> int:
    password_hash = _hash_password(password)
    normalized_company_ids = [int(value) for value in (company_ids or []) if str(value).isdigit()]
    primary_company_id = normalized_company_ids[0] if normalized_company_ids else company_id
    normalized_branch_ids = [int(value) for value in (branch_ids or []) if str(value).isdigit()]
    primary_branch_id = normalized_branch_ids[0] if normalized_branch_ids else branch_id
    user_id = execute_insert(
        "INSERT INTO users (username, password_hash, full_name, email, phone, company_id, branch_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (username.strip(), password_hash, full_name.strip(), email.strip(), phone.strip(), primary_company_id, primary_branch_id),
    )
    set_user_roles(user_id, role_codes or [])
    set_user_companies(user_id, normalized_company_ids if normalized_company_ids else ([primary_company_id] if primary_company_id else []))
    set_user_branches(user_id, normalized_branch_ids if normalized_branch_ids else ([primary_branch_id] if primary_branch_id else []))
    return user_id


def authenticate_user(username: str, password: str) -> sqlite3.Row | None:
    key = (username or "").strip()
    if not key:
        return None
    user = fetch_one(
        "SELECT "
        + USER_DETAIL_SELECT +
        "FROM users "
        "LEFT JOIN companies ON companies.id = users.company_id "
        "LEFT JOIN branches ON branches.id = users.branch_id "
        "WHERE (LOWER(users.username) = LOWER(?) OR LOWER(TRIM(COALESCE(users.email, ''))) = LOWER(?)) "
        "AND users.is_active = 1",
        (key, key),
    )
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def get_user_role_codes(user_id: int) -> list[str]:
    rows = fetch_all(
        "SELECT roles.code FROM roles "
        "INNER JOIN user_roles ON user_roles.role_id = roles.id "
        "WHERE user_roles.user_id = ? "
        "ORDER BY roles.name ASC",
        (user_id,),
    )
    return [row["code"] for row in rows]


def get_role_permission_codes(role_code: str) -> list[str]:
    rows = fetch_all(
        "SELECT permissions.code FROM permissions "
        "INNER JOIN role_permissions ON role_permissions.permission_id = permissions.id "
        "INNER JOIN roles ON roles.id = role_permissions.role_id "
        "WHERE roles.code = ? "
        "ORDER BY permissions.module_name ASC, permissions.name ASC",
        (role_code,),
    )
    return [row["code"] for row in rows]


def set_user_roles(user_id: int, role_codes: list[str]) -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))
        if role_codes:
            role_rows = connection.execute(
                f"SELECT id FROM roles WHERE code IN ({_sql_placeholders(len(role_codes))})",
                tuple(role_codes),
            ).fetchall()
            for row in role_rows:
                connection.execute(
                    _sql_insert_ignore("user_roles", ("user_id", "role_id")),
                    (user_id, row["id"]),
                )
        connection.commit()


def get_user_company_ids(user_id: int) -> list[int]:
    rows = fetch_all(
        "SELECT company_id FROM user_companies WHERE user_id = ? ORDER BY company_id ASC",
        (user_id,),
    )
    return [int(row["company_id"]) for row in rows]


def set_user_companies(user_id: int, company_ids: list[int]) -> None:
    unique_ids: list[int] = []
    for company_id in company_ids:
        try:
            normalized = int(company_id)
        except (TypeError, ValueError):
            continue
        if normalized not in unique_ids:
            unique_ids.append(normalized)
    primary_company_id = unique_ids[0] if unique_ids else None
    with get_connection() as connection:
        connection.execute("DELETE FROM user_companies WHERE user_id = ?", (user_id,))
        for company_id in unique_ids:
            connection.execute(
                _sql_insert_ignore("user_companies", ("user_id", "company_id")),
                (user_id, company_id),
            )
        connection.execute(
            "UPDATE users SET company_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (primary_company_id, user_id),
        )
        connection.commit()


def get_user_branch_ids(user_id: int) -> list[int]:
    rows = fetch_all(
        "SELECT branch_id FROM user_branches WHERE user_id = ? ORDER BY branch_id ASC",
        (user_id,),
    )
    return [int(row["branch_id"]) for row in rows]


def set_user_branches(user_id: int, branch_ids: list[int]) -> None:
    unique_ids: list[int] = []
    for branch_id in branch_ids:
        try:
            normalized = int(branch_id)
        except (TypeError, ValueError):
            continue
        if normalized not in unique_ids:
            unique_ids.append(normalized)
    primary_branch_id = unique_ids[0] if unique_ids else None
    with get_connection() as connection:
        connection.execute("DELETE FROM user_branches WHERE user_id = ?", (user_id,))
        for branch_id in unique_ids:
            connection.execute(
                _sql_insert_ignore("user_branches", ("user_id", "branch_id")),
                (user_id, branch_id),
            )
        connection.execute(
            "UPDATE users SET branch_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (primary_branch_id, user_id),
        )
        connection.commit()


def set_role_permissions(role_code: str, permission_codes: list[str]) -> None:
    with get_connection() as connection:
        role_row = connection.execute("SELECT id FROM roles WHERE code = ?", (role_code,)).fetchone()
        if not role_row:
            return
        role_id = role_row["id"]
        connection.execute("DELETE FROM role_permissions WHERE role_id = ?", (role_id,))
        if permission_codes:
            permission_rows = connection.execute(
                f"SELECT id FROM permissions WHERE code IN ({_sql_placeholders(len(permission_codes))})",
                tuple(permission_codes),
            ).fetchall()
            for row in permission_rows:
                connection.execute(
                    _sql_insert_ignore("role_permissions", ("role_id", "permission_id")),
                    (role_id, row["id"]),
                )
        connection.commit()


def update_user(
    user_id: int,
    username: str,
    full_name: str,
    email: str,
    phone: str,
    company_id: int | None,
    company_ids: list[int] | None,
    branch_id: int | None,
    branch_ids: list[int] | None,
    is_active: bool,
    role_codes: list[str],
    password: str = "",
) -> None:
    normalized_company_ids = [int(value) for value in (company_ids or []) if str(value).isdigit()]
    primary_company_id = normalized_company_ids[0] if normalized_company_ids else company_id
    normalized_branch_ids = [int(value) for value in (branch_ids or []) if str(value).isdigit()]
    primary_branch_id = normalized_branch_ids[0] if normalized_branch_ids else branch_id
    with get_connection() as connection:
        params = (
            username.strip(),
            full_name.strip(),
            email.strip(),
            phone.strip(),
            primary_company_id,
            primary_branch_id,
            1 if is_active else 0,
            user_id,
        )
        if password:
            connection.execute(
                "UPDATE users SET username = ?, full_name = ?, email = ?, phone = ?, company_id = ?, branch_id = ?, is_active = ?, password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (
                    username.strip(),
                    full_name.strip(),
                    email.strip(),
                    phone.strip(),
                    primary_company_id,
                    primary_branch_id,
                    1 if is_active else 0,
                    _hash_password(password),
                    user_id,
                ),
            )
        else:
            connection.execute(
                "UPDATE users SET username = ?, full_name = ?, email = ?, phone = ?, company_id = ?, branch_id = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                params,
            )
        connection.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))
        if role_codes:
            role_rows = connection.execute(
                f"SELECT id FROM roles WHERE code IN ({_sql_placeholders(len(role_codes))})",
                tuple(role_codes),
            ).fetchall()
            for row in role_rows:
                connection.execute(
                    _sql_insert_ignore("user_roles", ("user_id", "role_id")),
                    (user_id, row["id"]),
                )
        connection.commit()
    set_user_companies(user_id, normalized_company_ids if normalized_company_ids else ([primary_company_id] if primary_company_id else []))
    set_user_branches(user_id, normalized_branch_ids if normalized_branch_ids else ([primary_branch_id] if primary_branch_id else []))


def get_user_permissions(user_id: int) -> set[str]:
    rows = fetch_all(
        "SELECT DISTINCT permissions.code FROM permissions "
        "INNER JOIN role_permissions ON role_permissions.permission_id = permissions.id "
        "INNER JOIN user_roles ON user_roles.role_id = role_permissions.role_id "
        "WHERE user_roles.user_id = ?",
        (user_id,),
    )
    return {row["code"] for row in rows}


def get_record_user_share_ids(module_name: str, record_id: int) -> list[int]:
    rows = fetch_all(
        "SELECT user_id FROM record_user_shares WHERE module_name = ? AND record_id = ? ORDER BY user_id ASC",
        (module_name, record_id),
    )
    return [int(row["user_id"]) for row in rows]


def replace_record_user_shares(module_name: str, record_id: int, user_ids: list[int]) -> None:
    unique_ids = []
    for user_id in user_ids:
        if user_id not in unique_ids:
            unique_ids.append(user_id)
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM record_user_shares WHERE module_name = ? AND record_id = ?",
            (module_name, record_id),
        )
        for user_id in unique_ids:
            connection.execute(
                _sql_insert_ignore("record_user_shares", ("module_name", "record_id", "user_id")),
                (module_name, record_id, user_id),
            )
        connection.commit()


def get_record_role_share_ids(module_name: str, record_id: int) -> list[int]:
    rows = fetch_all(
        "SELECT role_id FROM record_role_shares WHERE module_name = ? AND record_id = ? ORDER BY role_id ASC",
        (module_name, record_id),
    )
    return [int(row["role_id"]) for row in rows]


def get_record_role_shares(module_name: str, record_id: int) -> list[sqlite3.Row]:
    return fetch_all(
        "SELECT roles.id, roles.code, roles.name "
        "FROM record_role_shares "
        "INNER JOIN roles ON roles.id = record_role_shares.role_id "
        "WHERE record_role_shares.module_name = ? AND record_role_shares.record_id = ? "
        "ORDER BY roles.name ASC",
        (module_name, record_id),
    )


def replace_record_role_shares(module_name: str, record_id: int, role_ids: list[int]) -> None:
    unique_ids = []
    for role_id in role_ids:
        if role_id not in unique_ids:
            unique_ids.append(role_id)
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM record_role_shares WHERE module_name = ? AND record_id = ?",
            (module_name, record_id),
        )
        for role_id in unique_ids:
            connection.execute(
                _sql_insert_ignore("record_role_shares", ("module_name", "record_id", "role_id")),
                (module_name, record_id, role_id),
            )
        connection.commit()


def user_has_meeting_access(meeting_id: int, user_id: int) -> bool:
    row = fetch_one("SELECT owner_user_id FROM meeting_notes WHERE id = ?", (meeting_id,))
    if not row:
        return False
    owner_id = row["owner_user_id"]
    if owner_id is not None and int(owner_id) == int(user_id):
        return True
    if fetch_one(
        "SELECT 1 AS ok FROM record_user_shares WHERE module_name = 'meetings' AND record_id = ? AND user_id = ?",
        (meeting_id, user_id),
    ):
        return True
    return bool(
        fetch_one(
            "SELECT 1 AS ok FROM record_role_shares "
            "INNER JOIN user_roles ON user_roles.role_id = record_role_shares.role_id "
            "WHERE record_role_shares.module_name = 'meetings' AND record_role_shares.record_id = ? "
            "AND user_roles.user_id = ?",
            (meeting_id, user_id),
        )
    )


def user_owns_meeting(meeting_id: int, user_id: int) -> bool:
    row = fetch_one("SELECT owner_user_id FROM meeting_notes WHERE id = ?", (meeting_id,))
    return bool(row and row["owner_user_id"] is not None and int(row["owner_user_id"]) == int(user_id))


def list_meeting_agenda_items(meeting_id: int) -> list[sqlite3.Row]:
    return fetch_all(
        "SELECT meeting_agenda_items.*, "
        "COALESCE(NULLIF(users.full_name, ''), NULLIF(users.username, ''), 'Kullanıcı') AS author_display "
        "FROM meeting_agenda_items "
        "LEFT JOIN users ON users.id = meeting_agenda_items.author_user_id "
        "WHERE meeting_agenda_items.meeting_id = ? "
        "ORDER BY meeting_agenda_items.id ASC",
        (meeting_id,),
    )


def insert_meeting_agenda_item(meeting_id: int, body: str, author_user_id: int) -> int:
    return execute_insert(
        "INSERT INTO meeting_agenda_items (meeting_id, body, author_user_id) VALUES (?, ?, ?)",
        (meeting_id, body.strip(), author_user_id),
    )


def get_meeting_agenda_item(item_id: int) -> sqlite3.Row | None:
    return fetch_one("SELECT * FROM meeting_agenda_items WHERE id = ?", (int(item_id),))


def update_meeting_agenda_item_body(item_id: int, body: str, editor_user_id: int, meeting_owner_id: int) -> bool:
    row = fetch_one("SELECT author_user_id FROM meeting_agenda_items WHERE id = ?", (int(item_id),))
    if not row:
        return False
    author = int(row["author_user_id"])
    if author != int(editor_user_id) and int(editor_user_id) != int(meeting_owner_id):
        return False
    execute(
        "UPDATE meeting_agenda_items SET body = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (body.strip(), int(item_id)),
    )
    return True


def delete_meeting_agenda_item(item_id: int) -> None:
    execute("DELETE FROM meeting_agenda_items WHERE id = ?", (int(item_id),))


def add_attachment(
    module_name: str,
    record_id: int,
    original_name: str,
    stored_name: str,
    file_path: str,
    mime_type: str,
    file_size: int,
    uploaded_by: int | None,
) -> int:
    return execute_insert(
        "INSERT INTO attachments (module_name, record_id, original_name, stored_name, file_path, mime_type, file_size, uploaded_by) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (module_name, record_id, original_name, stored_name, file_path, mime_type, file_size, uploaded_by),
    )


def list_attachments(module_name: str, record_id: int) -> list[sqlite3.Row]:
    return fetch_all(
        "SELECT attachments.*, users.full_name AS uploader_full_name, users.username AS uploader_username "
        "FROM attachments "
        "LEFT JOIN users ON users.id = attachments.uploaded_by "
        "WHERE attachments.module_name = ? AND attachments.record_id = ? "
        "ORDER BY attachments.created_at DESC, attachments.id DESC",
        (module_name, record_id),
    )


def get_attachment_count_map(module_name: str, record_ids: list[int]) -> dict[int, int]:
    unique_ids = [int(record_id) for record_id in dict.fromkeys(record_ids) if int(record_id) > 0]
    if not unique_ids:
        return {}
    placeholders = ", ".join("?" for _ in unique_ids)
    rows = fetch_all(
        f"SELECT record_id, COUNT(*) AS file_count FROM attachments "
        f"WHERE module_name = ? AND record_id IN ({placeholders}) "
        f"GROUP BY record_id",
        (module_name, *unique_ids),
    )
    return {int(row["record_id"]): int(row["file_count"]) for row in rows}


def get_attachment(attachment_id: int) -> sqlite3.Row | None:
    return fetch_one(
        "SELECT attachments.*, users.full_name AS uploader_full_name, users.username AS uploader_username "
        "FROM attachments "
        "LEFT JOIN users ON users.id = attachments.uploaded_by "
        "WHERE attachments.id = ?",
        (attachment_id,),
    )


def delete_attachment(attachment_id: int) -> None:
    execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))


def save_task_change_request(
    task_id: int,
    owner_user_id: int,
    requester_user_id: int,
    request_type: str,
    payload: dict | None = None,
) -> int:
    payload_json = json.dumps(payload or {}, ensure_ascii=False)
    existing = fetch_one(
        "SELECT id FROM task_change_requests "
        "WHERE task_id = ? AND requester_user_id = ? AND request_type = ? AND status = 'pending' "
        "ORDER BY id DESC LIMIT 1",
        (task_id, requester_user_id, request_type),
    )
    if existing:
        execute(
            "UPDATE task_change_requests "
            "SET payload = ?, owner_user_id = ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (payload_json, owner_user_id, int(existing["id"])),
        )
        return int(existing["id"])
    return execute_insert(
        "INSERT INTO task_change_requests (task_id, owner_user_id, requester_user_id, request_type, payload) "
        "VALUES (?, ?, ?, ?, ?)",
        (task_id, owner_user_id, requester_user_id, request_type, payload_json),
    )


def get_task_change_request(request_id: int) -> sqlite3.Row | None:
    return fetch_one("SELECT * FROM task_change_requests WHERE id = ?", (request_id,))


def list_pending_task_change_requests(owner_user_id: int) -> list[sqlite3.Row]:
    return fetch_all(
        "SELECT task_change_requests.*, tasks.title AS task_title, "
        "owner_user.full_name AS owner_full_name, owner_user.username AS owner_username, "
        "requester.full_name AS requester_full_name, requester.username AS requester_username "
        "FROM task_change_requests "
        "INNER JOIN tasks ON tasks.id = task_change_requests.task_id "
        "INNER JOIN users AS requester ON requester.id = task_change_requests.requester_user_id "
        "INNER JOIN users AS owner_user ON owner_user.id = task_change_requests.owner_user_id "
        "WHERE task_change_requests.owner_user_id = ? AND task_change_requests.status = 'pending' "
        "ORDER BY task_change_requests.created_at DESC, task_change_requests.id DESC",
        (owner_user_id,),
    )


def list_outgoing_pending_task_change_requests(requester_user_id: int) -> list[sqlite3.Row]:
    return fetch_all(
        "SELECT task_change_requests.*, tasks.title AS task_title, "
        "owner_user.full_name AS owner_full_name, owner_user.username AS owner_username "
        "FROM task_change_requests "
        "INNER JOIN tasks ON tasks.id = task_change_requests.task_id "
        "INNER JOIN users AS owner_user ON owner_user.id = task_change_requests.owner_user_id "
        "WHERE task_change_requests.requester_user_id = ? AND task_change_requests.status = 'pending' "
        "ORDER BY task_change_requests.created_at DESC, task_change_requests.id DESC",
        (requester_user_id,),
    )


def list_task_change_history_for_user(user_id: int, limit: int = 5) -> list[sqlite3.Row]:
    return fetch_all(
        "SELECT task_change_requests.*, tasks.title AS task_title, "
        "owner_user.full_name AS owner_full_name, owner_user.username AS owner_username, "
        "requester.full_name AS requester_full_name, requester.username AS requester_username, "
        "resolver.full_name AS resolver_full_name, resolver.username AS resolver_username "
        "FROM task_change_requests "
        "INNER JOIN tasks ON tasks.id = task_change_requests.task_id "
        "INNER JOIN users AS requester ON requester.id = task_change_requests.requester_user_id "
        "INNER JOIN users AS owner_user ON owner_user.id = task_change_requests.owner_user_id "
        "LEFT JOIN users AS resolver ON resolver.id = task_change_requests.resolved_by "
        "WHERE ("
        "    (task_change_requests.owner_user_id = ? AND task_change_requests.owner_hidden_at IS NULL) "
        "    OR "
        "    (task_change_requests.requester_user_id = ? AND task_change_requests.requester_hidden_at IS NULL)"
        ") "
        "ORDER BY task_change_requests.updated_at DESC, task_change_requests.id DESC "
        "LIMIT ?",
        (user_id, user_id, limit),
    )


def resolve_task_change_request(request_id: int, status: str, resolved_by: int) -> None:
    execute(
        "UPDATE task_change_requests "
        "SET status = ?, resolved_by = ?, resolved_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (status, resolved_by, request_id),
    )


def hide_task_change_history_items(user_id: int, request_ids: list[int]) -> None:
    if not request_ids:
        return
    placeholders = ",".join("?" for _ in request_ids)
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT id, owner_user_id, requester_user_id, status FROM task_change_requests WHERE id IN ({placeholders})",
            tuple(request_ids),
        ).fetchall()
        for row in rows:
            if row["status"] == "pending":
                continue
            if int(row["owner_user_id"]) == user_id:
                connection.execute(
                    "UPDATE task_change_requests SET owner_hidden_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (int(row["id"]),),
                )
            if int(row["requester_user_id"]) == user_id:
                connection.execute(
                    "UPDATE task_change_requests SET requester_hidden_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (int(row["id"]),),
                )
        connection.commit()


def hide_all_task_change_history_for_user(user_id: int) -> None:
    with get_connection() as connection:
        connection.execute(
            "UPDATE task_change_requests "
            "SET owner_hidden_at = CASE WHEN owner_user_id = ? THEN CURRENT_TIMESTAMP ELSE owner_hidden_at END, "
            "    requester_hidden_at = CASE WHEN requester_user_id = ? THEN CURRENT_TIMESTAMP ELSE requester_hidden_at END, "
            "    updated_at = CURRENT_TIMESTAMP "
            "WHERE status != 'pending' AND (owner_user_id = ? OR requester_user_id = ?)",
            (user_id, user_id, user_id, user_id),
        )
        connection.commit()


def save_document_change_request(
    document_id: int,
    document_kind: str,
    owner_user_id: int,
    requester_user_id: int,
    request_type: str,
    payload: dict | None = None,
) -> int:
    payload_json = json.dumps(payload or {}, ensure_ascii=False)
    existing = fetch_one(
        "SELECT id FROM document_change_requests "
        "WHERE document_id = ? AND document_kind = ? AND requester_user_id = ? AND request_type = ? AND status = 'pending' "
        "ORDER BY id DESC LIMIT 1",
        (document_id, document_kind, requester_user_id, request_type),
    )
    if existing:
        execute(
            "UPDATE document_change_requests "
            "SET payload = ?, owner_user_id = ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (payload_json, owner_user_id, int(existing["id"])),
        )
        return int(existing["id"])
    return execute_insert(
        "INSERT INTO document_change_requests (document_id, document_kind, owner_user_id, requester_user_id, request_type, payload) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (document_id, document_kind, owner_user_id, requester_user_id, request_type, payload_json),
    )


def get_document_change_request(request_id: int) -> sqlite3.Row | None:
    return fetch_one("SELECT * FROM document_change_requests WHERE id = ?", (request_id,))


def list_pending_document_change_requests(owner_user_id: int) -> list[sqlite3.Row]:
    return fetch_all(
        "SELECT document_change_requests.*, "
        "COALESCE(documents.title, recurring_documents.title, payload_doc.title, 'Evrak') AS document_title, "
        "owner_user.full_name AS owner_full_name, owner_user.username AS owner_username, "
        "requester.full_name AS requester_full_name, requester.username AS requester_username "
        "FROM document_change_requests "
        "LEFT JOIN documents ON documents.id = document_change_requests.document_id AND document_change_requests.document_kind = 'one_time' "
        "LEFT JOIN recurring_documents ON recurring_documents.id = document_change_requests.document_id AND document_change_requests.document_kind = 'recurring' "
        "LEFT JOIN (SELECT id, NULL AS title FROM document_change_requests) AS payload_doc ON payload_doc.id = document_change_requests.id "
        "INNER JOIN users AS requester ON requester.id = document_change_requests.requester_user_id "
        "INNER JOIN users AS owner_user ON owner_user.id = document_change_requests.owner_user_id "
        "WHERE document_change_requests.owner_user_id = ? AND document_change_requests.status = 'pending' "
        "ORDER BY document_change_requests.created_at DESC, document_change_requests.id DESC",
        (owner_user_id,),
    )


def list_outgoing_pending_document_change_requests(requester_user_id: int) -> list[sqlite3.Row]:
    return fetch_all(
        "SELECT document_change_requests.*, "
        "COALESCE(documents.title, recurring_documents.title, 'Evrak') AS document_title, "
        "owner_user.full_name AS owner_full_name, owner_user.username AS owner_username "
        "FROM document_change_requests "
        "LEFT JOIN documents ON documents.id = document_change_requests.document_id AND document_change_requests.document_kind = 'one_time' "
        "LEFT JOIN recurring_documents ON recurring_documents.id = document_change_requests.document_id AND document_change_requests.document_kind = 'recurring' "
        "INNER JOIN users AS owner_user ON owner_user.id = document_change_requests.owner_user_id "
        "WHERE document_change_requests.requester_user_id = ? AND document_change_requests.status = 'pending' "
        "ORDER BY document_change_requests.created_at DESC, document_change_requests.id DESC",
        (requester_user_id,),
    )


def list_document_change_history_for_user(user_id: int, limit: int = 5) -> list[sqlite3.Row]:
    return fetch_all(
        "SELECT document_change_requests.*, "
        "COALESCE(documents.title, recurring_documents.title, 'Evrak') AS document_title, "
        "owner_user.full_name AS owner_full_name, owner_user.username AS owner_username, "
        "requester.full_name AS requester_full_name, requester.username AS requester_username, "
        "resolver.full_name AS resolver_full_name, resolver.username AS resolver_username "
        "FROM document_change_requests "
        "LEFT JOIN documents ON documents.id = document_change_requests.document_id AND document_change_requests.document_kind = 'one_time' "
        "LEFT JOIN recurring_documents ON recurring_documents.id = document_change_requests.document_id AND document_change_requests.document_kind = 'recurring' "
        "INNER JOIN users AS requester ON requester.id = document_change_requests.requester_user_id "
        "INNER JOIN users AS owner_user ON owner_user.id = document_change_requests.owner_user_id "
        "LEFT JOIN users AS resolver ON resolver.id = document_change_requests.resolved_by "
        "WHERE ("
        "    (document_change_requests.owner_user_id = ? AND document_change_requests.owner_hidden_at IS NULL) "
        "    OR "
        "    (document_change_requests.requester_user_id = ? AND document_change_requests.requester_hidden_at IS NULL)"
        ") "
        "ORDER BY document_change_requests.updated_at DESC, document_change_requests.id DESC "
        "LIMIT ?",
        (user_id, user_id, limit),
    )


def resolve_document_change_request(request_id: int, status: str, resolved_by: int) -> None:
    execute(
        "UPDATE document_change_requests "
        "SET status = ?, resolved_by = ?, resolved_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (status, resolved_by, request_id),
    )


def hide_document_change_history_items(user_id: int, request_ids: list[int]) -> None:
    if not request_ids:
        return
    placeholders = ",".join("?" for _ in request_ids)
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT id, owner_user_id, requester_user_id, status FROM document_change_requests WHERE id IN ({placeholders})",
            tuple(request_ids),
        ).fetchall()
        for row in rows:
            if row["status"] == "pending":
                continue
            if int(row["owner_user_id"]) == user_id:
                connection.execute(
                    "UPDATE document_change_requests SET owner_hidden_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (int(row["id"]),),
                )
            if int(row["requester_user_id"]) == user_id:
                connection.execute(
                    "UPDATE document_change_requests SET requester_hidden_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (int(row["id"]),),
                )
        connection.commit()


def hide_all_document_change_history_for_user(user_id: int) -> None:
    with get_connection() as connection:
        connection.execute(
            "UPDATE document_change_requests "
            "SET owner_hidden_at = CASE WHEN owner_user_id = ? THEN CURRENT_TIMESTAMP ELSE owner_hidden_at END, "
            "    requester_hidden_at = CASE WHEN requester_user_id = ? THEN CURRENT_TIMESTAMP ELSE requester_hidden_at END, "
            "    updated_at = CURRENT_TIMESTAMP "
            "WHERE status != 'pending' AND (owner_user_id = ? OR requester_user_id = ?)",
            (user_id, user_id, user_id, user_id),
        )
        connection.commit()


def create_session(user_id: int, duration_days: int = SESSION_DURATION_DAYS) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now().replace(microsecond=0) + timedelta(days=duration_days)
    execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, expires_at.strftime("%Y-%m-%d %H:%M:%S")),
    )
    return token


def get_session_user(token: str) -> sqlite3.Row | None:
    if not token:
        return None
    with get_connection() as connection:
        session_cutoff = _sql_current_session_cutoff()
        connection.execute(f"DELETE FROM sessions WHERE expires_at < {session_cutoff}")
        connection.commit()
        row = connection.execute(
            f"SELECT user_id FROM sessions WHERE token = ? AND expires_at >= {session_cutoff}",
            (token,),
        ).fetchone()
        if row:
            return get_user_by_id(int(row["user_id"]))
    return None


def delete_session(token: str) -> None:
    if not token:
        return
    execute("DELETE FROM sessions WHERE token = ?", (token,))


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt, digest = stored_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    recalculated = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        int(iterations),
    ).hex()
    return hmac.compare_digest(recalculated, digest)


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest}"
