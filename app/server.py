from __future__ import annotations

import json
import os
import sys
import mimetypes
import secrets
import csv
from http.cookies import SimpleCookie
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO, StringIO
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse
from datetime import datetime, timedelta

from app import db
from app.views import (
    audit_logs_page,
    backup_settings_page,
    branches_page,
    companies_page,
    dashboard_page,
    file_settings_page,
    notification_settings_page,
    documents_dashboard_page_filtered,
    events_page,
    meetings_workspace_page_v3 as meetings_dashboard_page,
    meeting_templates_page,
    calendar_nav_bar,
    quick_event_form,
    render_event_calendar,
    render_event_year_calendar,
    format_event_levels,
    quick_document_form,
    suppliers_page as suppliers_dashboard_page,
    not_found_page,
    search_results_page,
    tasks_page,
    module_page,
    document_form,
    render_document_item,
    render_supplier_item,
    users_page,
    roles_page,
    permissions_page,
    notifications_page,
    format_datetime,
    login_page,
    row_value,
    setup_page,
    forbidden_page,
)


if getattr(sys, "frozen", False):
    BASE_RUNTIME_DIR = Path(getattr(sys, "_MEIPASS", Path(os.getcwd())))
    STATIC_DIR = BASE_RUNTIME_DIR / "static"
    ASSETS_DIR = BASE_RUNTIME_DIR / "assets"
else:
    BASE_RUNTIME_DIR = Path(__file__).resolve().parent.parent
    STATIC_DIR = BASE_RUNTIME_DIR / "static"
    ASSETS_DIR = BASE_RUNTIME_DIR / "assets"


AUTH_COOKIE_NAME = "mynotes_session"
UPLOADS_DIR = db.APP_DIR / "uploads"
MODULE_VIEW_PERMISSIONS = {
    "/tasks": "tasks.view",
    "/meetings": "meetings.view",
    "/documents": "documents.view",
    "/events": "events.view",
    "/suppliers": "suppliers.view",
    "/backup-settings": "roles.manage",
    "/backup-settings/download": "roles.manage",
    "/file-settings": "roles.manage",
    "/audit-logs": "roles.manage",
    "/audit-logs/export": "roles.manage",
    "/companies": "roles.manage",
    "/branches": "roles.manage",
    "/users": "users.manage",
    "/roles": "roles.manage",
    "/permissions": "roles.manage",
    "/meeting-templates": "roles.manage",
}
MODULE_ALLOWED_PATHS = {
    "tasks.view": "/tasks",
    "meetings.view": "/meetings",
    "documents.view": "/documents",
    "events.view": "/events",
    "suppliers.view": "/suppliers",
    "users.manage": "/users",
    "roles.manage": "/roles",
}


def _parse_int_list(values: list[str] | None) -> list[int]:
    parsed: list[int] = []
    for value in values or []:
        try:
            normalized = int(str(value).strip())
        except (TypeError, ValueError):
            continue
        if normalized not in parsed:
            parsed.append(normalized)
    return parsed


def _normalize_user_company_branch_selection(
    company_ids: list[int],
    branch_ids: list[int],
) -> tuple[list[int], list[int], str | None]:
    valid_branch_ids: list[int] = []
    derived_company_ids = list(company_ids)
    for branch_id in branch_ids:
        branch_row = db.get_branch_by_id(branch_id)
        if not branch_row:
            return [], [], "Seçilen şubelerden biri bulunamadı."
        branch_company_id = int(branch_row["company_id"])
        if branch_company_id not in derived_company_ids:
            derived_company_ids.append(branch_company_id)
        valid_branch_ids.append(branch_id)
    if not derived_company_ids:
        return [], valid_branch_ids, None
    for branch_id in valid_branch_ids:
        branch_row = db.get_branch_by_id(branch_id)
        if branch_row and int(branch_row["company_id"]) not in derived_company_ids:
            return [], [], "Şube seçimi firma ile uyuşmuyor."
    return derived_company_ids, valid_branch_ids, None


class MyNotesHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path in {"/health", "/healthz"}:
            self.respond(HTTPStatus.OK, b"ok", content_type="text/plain; charset=utf-8")
            return
        if parsed.path.startswith("/static/"):
            self.serve_static(parsed.path)
            return
        if parsed.path.startswith("/assets/"):
            self.serve_assets(parsed.path)
            return

        if db.count_users() == 0 and parsed.path != "/setup":
            self.redirect("/setup")
            return

        self.current_user = self.get_current_user()
        self.current_permissions = self.get_current_permissions()
        self.allowed_paths = self.get_allowed_paths()
        self.notification_badge_count = self.get_notification_badge_count()
        self.current_user = self.with_notification_badge(self.current_user)

        if parsed.path == "/login":
            if self.current_user:
                self.redirect("/")
                return
            self.respond(
                HTTPStatus.OK,
                login_page(
                    next_path=query.get("next", ["/"])[0],
                    info="Kurulum tamamlandı. Şimdi kullanıcı bilgilerinizle giriş yapın."
                    if query.get("setup", [""])[0] == "done"
                    else "",
                ),
            )
            return

        if parsed.path == "/logout":
            self.handle_logout()
            return

        if parsed.path == "/setup":
            if db.count_users() > 0:
                self.redirect("/login" if not self.current_user else "/")
                return
            self.respond(HTTPStatus.OK, setup_page())
            return

        if not self.current_user:
            next_path = quote(parsed.path + (f"?{parsed.query}" if parsed.query else ""))
            self.redirect(f"/login?next={next_path}")
            return

        required_permission = MODULE_VIEW_PERMISSIONS.get(parsed.path)
        if required_permission and required_permission not in self.current_permissions:
            self.respond(HTTPStatus.FORBIDDEN, forbidden_page(self.current_user, self.allowed_paths))
            return

        routes = {
            "/": self.dashboard,
            "/search": lambda: self.search_page(query),
            "/notifications": self.notifications_page,
            "/notification-settings": lambda: self.notification_settings_page(query),
            "/backup-settings": lambda: self.backup_settings_page(query),
            "/file-settings": lambda: self.file_settings_page(query),
            "/audit-logs": lambda: self.audit_logs_page(query),
            "/companies": lambda: self.companies_page(query),
            "/branches": lambda: self.branches_page(query),
            "/tasks": lambda: self.tasks_page(query),
            "/meetings": lambda: self.meetings_page(query),
            "/documents": lambda: self.documents_page(query),
            "/events": lambda: self.events_page(query),
            "/suppliers": lambda: self.suppliers_page(query),
            "/users": lambda: self.users_page(query),
            "/roles": lambda: self.roles_page(query),
            "/permissions": lambda: self.permissions_page(query),
            "/meeting-templates": lambda: self.meeting_templates_page(query),
            "/attachments/download": lambda: self.download_attachment(query),
            "/backup-settings/download": lambda: self.download_backup(query),
            "/audit-logs/export": lambda: self.export_audit_logs(query),
        }
        handler = routes.get(parsed.path)
        if handler is None:
            self.respond(HTTPStatus.NOT_FOUND, not_found_page(self.current_user, self.allowed_paths))
            return
        handler()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        parsed_body, form_data, uploaded_files = self.parse_request_body()

        self.current_user = self.get_current_user()
        self.current_permissions = self.get_current_permissions()
        self.allowed_paths = self.get_allowed_paths()
        self.notification_badge_count = self.get_notification_badge_count()
        self.current_user = self.with_notification_badge(self.current_user)

        if parsed.path == "/setup":
            self.handle_setup(form_data)
            return

        if parsed.path == "/login":
            self.handle_login(form_data)
            return

        if db.count_users() == 0:
            self.redirect("/setup")
            return

        if not self.current_user:
            next_path = quote(parsed.path)
            self.redirect(f"/login?next={next_path}")
            return

        if not self._can_post_to(parsed.path):
            self.respond(HTTPStatus.FORBIDDEN, forbidden_page(self.current_user, self.allowed_paths))
            return

        # POST Request Dispatcher
        post_routes = {
            "/tasks": lambda: self._handle_task_create(form_data, parsed_body),
            "/tasks/toggle": lambda: self._handle_task_toggle(form_data),
            "/tasks/update": lambda: self._handle_task_update(form_data, parsed_body),
            "/tasks/delete": lambda: self._handle_task_delete(form_data),
            "/tasks/requests/approve": lambda: self._handle_task_approve(form_data),
            "/tasks/requests/reject": lambda: self._handle_task_reject(form_data),
            "/tasks/requests/history/delete": lambda: self._handle_task_history_delete(form_data, parsed_body),
            "/tasks/requests/history/clear": self._handle_task_history_clear,
            "/meetings": lambda: self._handle_meeting_create(form_data, parsed_body, uploaded_files),
            "/meetings/update": lambda: self._handle_meeting_update(form_data, parsed_body),
            "/meetings/delete": lambda: self._handle_meeting_delete(form_data),
            "/meetings/attachments": lambda: self._handle_meeting_attachment(form_data, uploaded_files),
            "/documents": lambda: self._handle_document_create(form_data, parsed_body, uploaded_files),
            "/documents/update": lambda: self._handle_document_update(form_data, parsed_body),
            "/documents/delete": lambda: self._handle_document_delete(form_data),
            "/users": lambda: self._handle_user_create(form_data, parsed_body),
            "/users/update": lambda: self._handle_user_update(form_data, parsed_body),
            "/users/toggle-active": lambda: self._handle_user_toggle(form_data),
        }

        handler = post_routes.get(parsed.path)
        if handler:
            handler()
            return
        # Eski devasa if-elif zinciri metodlara taşındı...
        elif parsed.path == "/attachments/delete":
            attachment_id = form_data.get("attachment_id", "").strip()
            module_name = form_data.get("module_name", "").strip()
            record_id = form_data.get("record_id", "").strip()
            attachment_name = ""
            if attachment_id.isdigit():
                attachment = db.get_attachment(int(attachment_id))
                if attachment:
                    attachment_name = str(attachment["original_name"] or attachment["stored_name"] or "")
                    try:
                        file_path = Path(attachment["file_path"])
                        if file_path.exists():
                            file_path.unlink()
                    except OSError:
                        pass
                    db.delete_attachment(int(attachment_id))
                    module_label = {
                        "meetings": "Toplantılar",
                        "documents": "Evraklar",
                        "recurring_documents": "Evraklar",
                    }.get(module_name, "Dosyalar")
                    self.audit("Dosya Silindi", module_label, int(record_id) if record_id.isdigit() else None, attachment_name)
            if module_name == "meetings" and record_id.isdigit():
                self.redirect(f"/meetings?meeting={record_id}&info=attachment_deleted")
                return
            if module_name in {"documents", "recurring_documents"} and record_id.isdigit():
                source_kind = "recurring" if module_name == "recurring_documents" else "one_time"
                self.redirect(f"/documents?edit_kind={source_kind}&edit_id={record_id}&info=attachment_deleted")
                return
        elif parsed.path == "/meeting-templates":
            title = form_data.get("title", "").strip()
            if title:
                current_max = db.fetch_one("SELECT COALESCE(MAX(sort_order), 0) AS value FROM meeting_templates")
                next_order = int(current_max["value"]) + 1 if current_max else 1
                db.execute(
                    "INSERT OR IGNORE INTO meeting_templates (title, sort_order) VALUES (?, ?)",
                    (title, next_order),
                )
                self.audit("Başlık Eklendi", "Toplantı Ayarları", details=title)
                self.redirect("/meeting-templates?info=template_saved")
                return
            self.redirect("/meeting-templates?error=template_missing")
            return
        elif parsed.path == "/meeting-templates/delete":
            template_id = form_data.get("id", "").strip()
            if template_id.isdigit():
                target_template = db.fetch_one("SELECT * FROM meeting_templates WHERE id = ?", (int(template_id),))
                db.execute("DELETE FROM meeting_templates WHERE id = ?", (int(template_id),))
                if target_template:
                    self.audit("Başlık Silindi", "Toplantı Ayarları", int(template_id), str(target_template["title"]))
                self.redirect("/meeting-templates?info=template_deleted")
                return
            self.redirect("/meeting-templates?error=template_missing")
            return
        elif parsed.path == "/meetings/task":
            meeting_id = form_data.get("meeting_id", "").strip()
            decision_text = form_data.get("decision_text", "").strip()
            if decision_text and meeting_id.isdigit():
                existing_task = db.fetch_one(
                    "SELECT id FROM tasks WHERE related_type = 'meeting' AND related_id = ? AND title = ?",
                    (int(meeting_id), decision_text),
                )
                if not existing_task:
                    db.execute(
                        "INSERT INTO tasks (title, responsible_person, description, category, priority, status, due_date, related_type, related_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            decision_text,
                            "",
                            "",
                            "Toplantı",
                            "medium",
                            "pending",
                            "",
                            "meeting",
                            int(meeting_id),
                        ),
                    )
                    self.audit("Toplantı Kararından Görev Oluşturuldu", "Toplantılar", int(meeting_id), decision_text)
        elif parsed.path == "/documents":
            kind = form_data.get("kind", "one_time").strip()
            frequency = form_data.get("frequency", "monthly").strip()
            description = form_data.get("description", "").strip()
            current_user_id = int(self.current_user["id"])
            share_user_ids = _normalize_share_user_ids(parsed_body.get("share_user_ids", []), current_user_id)
            share_role_ids = _normalize_share_role_ids(parsed_body.get("share_role_ids", []))
            visibility_type = "shared" if share_user_ids or share_role_ids else "private"
            upload = uploaded_files.get("attachment")
            if upload and upload.get("filename") and upload.get("content"):
                validation_error = _validate_uploaded_file(upload, db.get_file_settings())
                if validation_error:
                    self.redirect(f"/documents?error={quote(validation_error)}")
                    return
            if kind == "one_time":
                title = form_data.get("title", "").strip()
                next_due_date = form_data.get("next_due_date", "").strip()
                document_id = db.execute_insert(
                    "INSERT INTO documents (title, institution, document_type, description, status, due_date, responsible_person, owner_user_id, visibility_type, created_by, updated_by) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        title,
                        "",
                        "Genel Evrak",
                        description,
                        "waiting",
                        next_due_date,
                        form_data.get("responsible_person", "").strip(),
                        current_user_id,
                        visibility_type,
                        current_user_id,
                        current_user_id,
                    ),
                )
                db.replace_record_user_shares("documents", document_id, share_user_ids)
                db.replace_record_role_shares("documents", document_id, share_role_ids)
                attachment_module = "documents"
            else:
                title = form_data.get("title", "").strip()
                next_due_date = form_data.get("next_due_date", "").strip()
                document_id = db.execute_insert(
                    "INSERT INTO recurring_documents (title, category, frequency, next_due_date, responsible_person, notes, owner_user_id, visibility_type, created_by, updated_by) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        title,
                        "Genel",
                        frequency,
                        next_due_date,
                        form_data.get("responsible_person", "").strip(),
                        description,
                        current_user_id,
                        visibility_type,
                        current_user_id,
                        current_user_id,
                    ),
                )
                db.replace_record_user_shares("recurring_documents", document_id, share_user_ids)
                db.replace_record_role_shares("recurring_documents", document_id, share_role_ids)
                attachment_module = "recurring_documents"
            kind_label = "Tekrarlı Evrak" if kind == "recurring" else "Evrak"
            self.audit("Evrak Eklendi", "Evraklar", document_id, f"{title} • {kind_label}{f' • Termin: {next_due_date}' if next_due_date else ''}")
            if upload and upload.get("filename") and upload.get("content"):
                target_dir = UPLOADS_DIR / attachment_module / str(document_id)
                target_dir.mkdir(parents=True, exist_ok=True)
                safe_name = _sanitize_filename(upload["filename"])
                stored_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}_{safe_name}"
                target_path = target_dir / stored_name
                target_path.write_bytes(upload["content"])
                mime_type = upload.get("content_type") or mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
                db.add_attachment(
                    attachment_module,
                    int(document_id),
                    upload["filename"],
                    stored_name,
                    str(target_path),
                    mime_type,
                    len(upload["content"]),
                    current_user_id,
                )
                self.audit("Evrak Dosyası Eklendi", "Evraklar", int(document_id), upload["filename"])
                self.redirect("/documents?info=document_created_with_attachment")
                return
            self.redirect("/documents?info=document_created")
            return
        elif parsed.path == "/documents/attachments":
            item_id = form_data.get("document_id", "").strip()
            module_name = form_data.get("kind", "").strip()
            if item_id.isdigit() and module_name in {"documents", "recurring_documents"}:
                source_kind = "recurring" if module_name == "recurring_documents" else "one_time"
                document_row = _fetch_document_row(int(item_id), source_kind)
                current_user_id = int(self.current_user["id"])
                is_admin = "admin" in db.get_user_role_codes(current_user_id)
                upload = uploaded_files.get("attachment")
                if not document_row or not _can_manage_document_directly(document_row, current_user_id, is_admin):
                    self.redirect("/documents?error=document_missing")
                    return
                if upload and upload.get("filename") and upload.get("content"):
                    validation_error = _validate_uploaded_file(upload, db.get_file_settings())
                    if validation_error:
                        self.redirect(f"/documents?edit_kind={source_kind}&edit_id={item_id}&error={quote(validation_error)}")
                        return
                    target_dir = UPLOADS_DIR / module_name / item_id
                    target_dir.mkdir(parents=True, exist_ok=True)
                    safe_name = _sanitize_filename(upload["filename"])
                    stored_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}_{safe_name}"
                    target_path = target_dir / stored_name
                    target_path.write_bytes(upload["content"])
                    mime_type = upload.get("content_type") or mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
                    db.add_attachment(
                        module_name,
                        int(item_id),
                        upload["filename"],
                        stored_name,
                        str(target_path),
                        mime_type,
                        len(upload["content"]),
                        current_user_id,
                    )
                    self.audit("Evrak Dosyası Eklendi", "Evraklar", int(item_id), upload["filename"])
                    self.redirect(f"/documents?edit_kind={source_kind}&edit_id={item_id}&info=attachment_uploaded")
                    return
                self.redirect(f"/documents?edit_kind={source_kind}&edit_id={item_id}&error=attachment_missing")
                return
        elif parsed.path == "/documents/update":
            item_id = form_data.get("id", "").strip()
            target_kind = form_data.get("kind", "one_time").strip()
            frequency = form_data.get("frequency", "monthly").strip()
            source_kind = form_data.get("source_kind", target_kind).strip()
            current_user_id = int(self.current_user["id"])
            if item_id.isdigit():
                is_admin = "admin" in db.get_user_role_codes(current_user_id)
                document_row = _fetch_document_row(int(item_id), source_kind)
                if not document_row:
                    self.redirect("/documents?error=document_missing")
                    return
                share_user_ids = _normalize_share_user_ids(parsed_body.get("share_user_ids", []), current_user_id)
                share_role_ids = _normalize_share_role_ids(parsed_body.get("share_role_ids", []))
                visibility_type = "shared" if share_user_ids or share_role_ids else "private"
                if _can_manage_document_directly(document_row, current_user_id, is_admin):
                    previous_title = document_row["title"]
                    _apply_document_update(
                        int(item_id),
                        source_kind,
                        target_kind,
                        form_data.get("title", "").strip(),
                        frequency,
                        form_data.get("next_due_date", "").strip(),
                        form_data.get("description", "").strip(),
                        current_user_id,
                        int(document_row["owner_user_id"]) if document_row["owner_user_id"] else current_user_id,
                        share_user_ids,
                        share_role_ids,
                        visibility_type,
                    )
                    self.audit("Evrak Güncellendi", "Evraklar", int(item_id), f"{previous_title} -> {form_data.get('title', '').strip()}")
                    self.redirect("/documents?info=document_updated")
                    return
                if not _can_request_document_change(document_row, source_kind, current_user_id):
                    self.redirect("/documents?error=document_missing")
                    return
                owner_user_id = int(document_row["owner_user_id"]) if document_row["owner_user_id"] else 0
                db.save_document_change_request(
                    int(item_id),
                    source_kind,
                    owner_user_id,
                    current_user_id,
                    "update",
                    {
                        "source_kind": source_kind,
                        "target_kind": target_kind,
                        "title": form_data.get("title", "").strip(),
                        "frequency": frequency,
                        "next_due_date": form_data.get("next_due_date", "").strip(),
                        "description": form_data.get("description", "").strip(),
                    },
                )
                self.audit("Evrak Düzenleme Talebi Gönderildi", "Evraklar", int(item_id), str(document_row["title"]))
                self.redirect("/documents?info=document_request_sent")
                return
        elif parsed.path == "/documents/delete":
            item_id = form_data.get("id", "").strip()
            kind = form_data.get("kind", "").strip()
            if item_id.isdigit() and kind == "one_time":
                current_user_id = int(self.current_user["id"])
                is_admin = "admin" in db.get_user_role_codes(current_user_id)
                document_row = _fetch_document_row(int(item_id), kind)
                if not document_row:
                    self.redirect("/documents?error=document_missing")
                    return
                if _can_manage_document_directly(document_row, current_user_id, is_admin):
                    _delete_document_record(int(item_id), kind)
                    self.audit("Evrak Silindi", "Evraklar", int(item_id), str(document_row["title"]))
                    self.redirect("/documents?info=document_deleted")
                    return
                if not _can_request_document_change(document_row, kind, current_user_id):
                    self.redirect("/documents?error=document_missing")
                    return
                owner_user_id = int(document_row["owner_user_id"]) if document_row["owner_user_id"] else 0
                db.save_document_change_request(
                    int(item_id),
                    kind,
                    owner_user_id,
                    current_user_id,
                    "delete",
                    {"title": document_row["title"], "source_kind": kind},
                )
                self.audit("Evrak Silme Talebi Gönderildi", "Evraklar", int(item_id), str(document_row["title"]))
                self.redirect("/documents?info=document_request_sent")
                return
            elif item_id.isdigit() and kind == "recurring":
                current_user_id = int(self.current_user["id"])
                is_admin = "admin" in db.get_user_role_codes(current_user_id)
                document_row = _fetch_document_row(int(item_id), kind)
                if not document_row:
                    self.redirect("/documents?error=document_missing")
                    return
                if _can_manage_document_directly(document_row, current_user_id, is_admin):
                    _delete_document_record(int(item_id), kind)
                    self.audit("Evrak Silindi", "Evraklar", int(item_id), str(document_row["title"]))
                    self.redirect("/documents?info=document_deleted")
                    return
                if not _can_request_document_change(document_row, kind, current_user_id):
                    self.redirect("/documents?error=document_missing")
                    return
                owner_user_id = int(document_row["owner_user_id"]) if document_row["owner_user_id"] else 0
                db.save_document_change_request(
                    int(item_id),
                    kind,
                    owner_user_id,
                    current_user_id,
                    "delete",
                    {"title": document_row["title"], "source_kind": kind},
                )
                self.audit("Evrak Silme Talebi Gönderildi", "Evraklar", int(item_id), str(document_row["title"]))
                self.redirect("/documents?info=document_request_sent")
                return
        elif parsed.path == "/documents/requests/approve":
            request_id = form_data.get("request_id", "").strip()
            if request_id.isdigit():
                current_user_id = int(self.current_user["id"])
                request_row = db.get_document_change_request(int(request_id))
                is_admin = "admin" in db.get_user_role_codes(current_user_id)
                if request_row and request_row["status"] == "pending" and (is_admin or int(request_row["owner_user_id"]) == current_user_id):
                    try:
                        payload = json.loads(request_row["payload"] or "{}")
                    except json.JSONDecodeError:
                        payload = {}
                    if request_row["request_type"] == "update":
                        existing_share_ids = db.get_record_user_share_ids(
                            "recurring_documents" if request_row["document_kind"] == "recurring" else "documents",
                            int(request_row["document_id"]),
                        )
                        row = _fetch_document_row(int(request_row["document_id"]), request_row["document_kind"])
                        visibility_type = row["visibility_type"] if row and row["visibility_type"] else ("shared" if existing_share_ids else "private")
                        _apply_document_update(
                            int(request_row["document_id"]),
                            payload.get("source_kind", request_row["document_kind"]),
                            payload.get("target_kind", request_row["document_kind"]),
                            payload.get("title", row["title"] if row else ""),
                            payload.get("frequency", row["frequency"] if row and request_row["document_kind"] == "recurring" else "monthly"),
                            payload.get("next_due_date", row["next_due_date"] if row and request_row["document_kind"] == "recurring" else row["due_date"] if row else ""),
                        payload.get("description", row["notes"] if row and request_row["document_kind"] == "recurring" else row["description"] if row else ""),
                        current_user_id,
                        int(request_row["owner_user_id"]),
                        existing_share_ids,
                        db.get_record_role_share_ids("recurring_documents" if request_row["document_kind"] == "recurring" else "documents", int(request_row["document_id"])),
                        visibility_type,
                    )
                    elif request_row["request_type"] == "delete":
                        _delete_document_record(int(request_row["document_id"]), request_row["document_kind"])
                    db.resolve_document_change_request(int(request_id), "approved", current_user_id)
                    self.audit(
                        "Evrak Talebi Onaylandı",
                        "Evraklar",
                        int(request_row["document_id"]),
                        f"{request_row['request_type']} • {request_row['document_title']}",
                    )
                    self.redirect("/documents?info=document_request_approved")
                    return
        elif parsed.path == "/documents/requests/reject":
            request_id = form_data.get("request_id", "").strip()
            if request_id.isdigit():
                current_user_id = int(self.current_user["id"])
                request_row = db.get_document_change_request(int(request_id))
                is_admin = "admin" in db.get_user_role_codes(current_user_id)
                if request_row and request_row["status"] == "pending" and (is_admin or int(request_row["owner_user_id"]) == current_user_id):
                    db.resolve_document_change_request(int(request_id), "rejected", current_user_id)
                    self.audit(
                        "Evrak Talebi Reddedildi",
                        "Evraklar",
                        int(request_row["document_id"]),
                        f"{request_row['request_type']} • {request_row['document_title']}",
                    )
                    self.redirect("/documents?info=document_request_rejected")
                    return
        elif parsed.path == "/documents/requests/history/delete":
            current_user_id = int(self.current_user["id"])
            request_id = form_data.get("request_id", "").strip()
            selected_ids = [value.strip() for value in parsed_body.get("request_ids", []) if value.strip().isdigit()]
            request_ids: list[int] = []
            if request_id.isdigit():
                request_ids.append(int(request_id))
            request_ids.extend(int(value) for value in selected_ids if int(value) not in request_ids)
            if request_ids:
                db.hide_document_change_history_items(current_user_id, request_ids)
                self.redirect("/documents?info=document_request_history_deleted")
                return
            self.redirect("/documents?error=document_request_history_empty")
            return
        elif parsed.path == "/documents/requests/history/clear":
            current_user_id = int(self.current_user["id"])
            db.hide_all_document_change_history_for_user(current_user_id)
            self.redirect("/documents?info=document_request_history_cleared")
            return
        elif parsed.path == "/documents/toggle":
            item_id = form_data.get("id", "").strip()
            kind = form_data.get("kind", "").strip()
            next_state = form_data.get("next_state", "done").strip()
            if item_id.isdigit() and kind == "one_time":
                row = db.fetch_one("SELECT id, title FROM documents WHERE id = ?", (int(item_id),))
                if next_state == "done":
                    db.execute(
                        "UPDATE documents SET status = 'submitted', submitted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (int(item_id),),
                    )
                else:
                    db.execute(
                        "UPDATE documents SET status = 'waiting', submitted_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (int(item_id),),
                    )
                if row:
                    action = "Evrak Tamamlandı" if next_state == "done" else "Evrak Yeniden Açıldı"
                    self.audit(action, "Evraklar", int(item_id), str(row["title"]))
            elif item_id.isdigit() and kind == "recurring":
                row = db.fetch_one("SELECT * FROM recurring_documents WHERE id = ?", (int(item_id),))
                if row:
                    if next_state == "done":
                        next_due_date = _advance_due_date(row["next_due_date"], row["frequency"], row["custom_interval_days"])
                        db.execute(
                            "UPDATE recurring_documents SET last_completed_at = CURRENT_TIMESTAMP, next_due_date = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                            (next_due_date, int(item_id)),
                        )
                    else:
                        db.execute(
                            "UPDATE recurring_documents SET last_completed_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                            (int(item_id),),
                        )
                    action = "Tekrarlı Evrak Tamamlandı" if next_state == "done" else "Tekrarlı Evrak Yeniden Açıldı"
                    self.audit(action, "Evraklar", int(item_id), str(row["title"]))
        elif parsed.path == "/recurring-documents":
            db.execute(
                "INSERT INTO recurring_documents (title, category, frequency, next_due_date, reminder_days_before, responsible_person, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    form_data.get("title", "").strip(),
                    form_data.get("category", "").strip(),
                    form_data.get("frequency", "monthly"),
                    form_data.get("next_due_date", "").strip(),
                    int(form_data.get("reminder_days_before", "7") or 7),
                    form_data.get("responsible_person", "").strip(),
                    form_data.get("notes", "").strip(),
                ),
            )
        elif parsed.path == "/suppliers":
            phone = _normalize_phone(form_data.get("phone", "").strip())
            company_name = form_data.get("company_name", "").strip()
            db.execute(
                "INSERT INTO suppliers (company_name, contact_name, phone, email, service_type, price_notes, notes, next_contact_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    company_name,
                    form_data.get("contact_name", "").strip(),
                    phone,
                    "",
                    form_data.get("service_type", "").strip(),
                    "",
                    "",
                    "",
                ),
            )
            _cleanup_supplier_phone()
            supplier_row = db.fetch_one("SELECT id FROM suppliers ORDER BY id DESC LIMIT 1")
            self.audit("Tedarikçi Eklendi", "Tedarikçiler", int(supplier_row["id"]) if supplier_row else None, company_name)
        elif parsed.path == "/suppliers/update":
            item_id = form_data.get("id", "").strip()
            if item_id.isdigit():
                phone = _normalize_phone(form_data.get("phone", "").strip())
                current_row = db.fetch_one("SELECT id, company_name FROM suppliers WHERE id = ?", (int(item_id),))
                db.execute(
                    "UPDATE suppliers SET company_name = ?, contact_name = ?, phone = ?, service_type = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (
                        form_data.get("company_name", "").strip(),
                        form_data.get("contact_name", "").strip(),
                        phone,
                        form_data.get("service_type", "").strip(),
                        int(item_id),
                    ),
                )
                _cleanup_supplier_phone()
                if current_row:
                    self.audit("Tedarikçi Güncellendi", "Tedarikçiler", int(item_id), f"{current_row['company_name']} -> {form_data.get('company_name', '').strip()}")
        elif parsed.path == "/suppliers/delete":
            item_id = form_data.get("id", "").strip()
            if item_id.isdigit():
                current_row = db.fetch_one("SELECT id, company_name FROM suppliers WHERE id = ?", (int(item_id),))
                db.execute("DELETE FROM supplier_interactions WHERE supplier_id = ?", (int(item_id),))
                db.execute("DELETE FROM suppliers WHERE id = ?", (int(item_id),))
                if current_row:
                    self.audit("Tedarikçi Silindi", "Tedarikçiler", int(item_id), str(current_row["company_name"]))
        elif parsed.path == "/supplier-notes":
            supplier_id = form_data.get("supplier_id", "").strip()
            if supplier_id.isdigit():
                supplier_row = db.fetch_one("SELECT id, company_name FROM suppliers WHERE id = ?", (int(supplier_id),))
                db.execute(
                    "INSERT INTO supplier_interactions (supplier_id, interaction_date, notes) VALUES (?, ?, ?)",
                    (
                        int(supplier_id),
                        form_data.get("interaction_date", "").strip(),
                        form_data.get("notes", "").strip(),
                    ),
                )
                if supplier_row:
                    self.audit("Tedarikçi Notu Eklendi", "Tedarikçiler", int(supplier_id), str(supplier_row["company_name"]))
        elif parsed.path == "/supplier-notes/update":
            supplier_id = form_data.get("supplier_id", "").strip()
            note_id = form_data.get("note_id", "").strip()
            if supplier_id.isdigit() and note_id.isdigit():
                supplier_row = db.fetch_one("SELECT id, company_name FROM suppliers WHERE id = ?", (int(supplier_id),))
                db.execute(
                    "UPDATE supplier_interactions SET interaction_date = ?, notes = ? WHERE id = ? AND supplier_id = ?",
                    (
                        form_data.get("interaction_date", "").strip(),
                        form_data.get("notes", "").strip(),
                        int(note_id),
                        int(supplier_id),
                    ),
                )
                if supplier_row:
                    self.audit("Tedarikçi Notu Güncellendi", "Tedarikçiler", int(supplier_id), str(supplier_row["company_name"]))
        elif parsed.path == "/supplier-notes/delete":
            supplier_id = form_data.get("supplier_id", "").strip()
            note_id = form_data.get("note_id", "").strip()
            if supplier_id.isdigit() and note_id.isdigit():
                supplier_row = db.fetch_one("SELECT id, company_name FROM suppliers WHERE id = ?", (int(supplier_id),))
                db.execute(
                    "DELETE FROM supplier_interactions WHERE id = ? AND supplier_id = ?",
                    (int(note_id), int(supplier_id)),
                )
                if supplier_row:
                    self.audit("Tedarikçi Notu Silindi", "Tedarikçiler", int(supplier_id), str(supplier_row["company_name"]))
        elif parsed.path == "/events":
            event_levels = _normalize_event_levels(parsed_body.get("level", []))
            start_date = form_data.get("event_date", "").strip()
            end_date = form_data.get("end_date", "").strip() or start_date
            title = form_data.get("title", "").strip()
            time_range = form_data.get("time_range", "").strip()
            notes = form_data.get("notes", "").strip()
            db.execute(
                "INSERT INTO events (title, event_date, end_date, level, time_range, notes) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    title,
                    start_date,
                    end_date,
                    ",".join(event_levels),
                    time_range,
                    notes,
                ),
            )
            event_row = db.fetch_one("SELECT id FROM events ORDER BY id DESC LIMIT 1")
            self.audit("Etkinlik Eklendi", "Etkinlikler", int(event_row["id"]) if event_row else None, f"{title} • {_format_date_range(start_date, end_date)}")
        elif parsed.path == "/events/update":
            item_id = form_data.get("id", "").strip()
            if item_id.isdigit():
                event_levels = _normalize_event_levels(parsed_body.get("level", []))
                start_date = form_data.get("event_date", "").strip()
                end_date = form_data.get("end_date", "").strip() or start_date
                time_range = form_data.get("time_range", "").strip()
                notes = form_data.get("notes", "").strip()
                current_row = db.fetch_one("SELECT id, title FROM events WHERE id = ?", (int(item_id),))
                db.execute(
                    "UPDATE events SET title = ?, event_date = ?, end_date = ?, level = ?, time_range = ?, notes = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (
                        form_data.get("title", "").strip(),
                        start_date,
                        end_date,
                        ",".join(event_levels),
                        time_range,
                        notes,
                        int(item_id),
                    ),
                )
                if current_row:
                    self.audit("Etkinlik Güncellendi", "Etkinlikler", int(item_id), f"{current_row['title']} -> {form_data.get('title', '').strip()}")
        elif parsed.path == "/events/delete":
            item_id = form_data.get("id", "").strip()
            if item_id.isdigit():
                current_row = db.fetch_one("SELECT id, title FROM events WHERE id = ?", (int(item_id),))
                db.execute("DELETE FROM events WHERE id = ?", (int(item_id),))
                if current_row:
                    self.audit("Etkinlik Silindi", "Etkinlikler", int(item_id), str(current_row["title"]))
        elif parsed.path == "/users":
            full_name = form_data.get("full_name", "").strip()
            username = form_data.get("username", "").strip()
            email = form_data.get("email", "").strip()
            phone = form_data.get("phone", "").strip()
            password = form_data.get("password", "")
            selected_company_ids = _parse_int_list(parsed_body.get("company_ids", []))
            selected_branch_ids = _parse_int_list(parsed_body.get("branch_ids", []))
            role_code = form_data.get("role_code", "ogretmen").strip()
            is_active = form_data.get("is_active", "1").strip() == "1"
            normalized_company_ids, normalized_branch_ids, relation_error = _normalize_user_company_branch_selection(selected_company_ids, selected_branch_ids)
            defaults = {
                "full_name": full_name,
                "username": username,
                "email": email,
                "phone": phone,
                "company_ids": [str(value) for value in normalized_company_ids or selected_company_ids],
                "branch_ids": [str(value) for value in normalized_branch_ids or selected_branch_ids],
                "role_code": role_code or "ogretmen",
                "is_active": "1" if is_active else "0",
            }
            if relation_error:
                self.render_users_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": relation_error},
                    form_defaults=defaults,
                )
                return
            company_id = normalized_company_ids[0] if normalized_company_ids else None
            branch_id = normalized_branch_ids[0] if normalized_branch_ids else None
            if not full_name or not username or not password:
                self.render_users_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Ad soyad, kullanıcı adı ve şifre zorunludur."},
                    form_defaults=defaults,
                )
                return
            if len(password) < 6:
                self.render_users_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Şifre en az 6 karakter olmalı."},
                    form_defaults=defaults,
                )
                return
            if db.get_user_by_username(username):
                self.render_users_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Bu kullanıcı adı zaten kullanılıyor."},
                    form_defaults=defaults,
                )
                return
            if email and db.get_user_by_email(email):
                self.render_users_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Bu e-posta başka bir kullanıcıda kayıtlı."},
                    form_defaults=defaults,
                )
                return
            try:
                user_id = db.create_user(
                    username=username,
                    password=password,
                    full_name=full_name,
                    email=email,
                    phone=phone,
                    company_id=company_id,
                    company_ids=normalized_company_ids,
                    branch_id=branch_id,
                    branch_ids=normalized_branch_ids,
                    role_codes=[role_code],
                )
                if not is_active:
                    db.update_user(
                        user_id=user_id,
                        username=username,
                        full_name=full_name,
                        email=email,
                        phone=phone,
                        company_id=company_id,
                        company_ids=normalized_company_ids,
                        branch_id=branch_id,
                        branch_ids=normalized_branch_ids,
                        is_active=False,
                        role_codes=[role_code],
                    )
            except Exception:
                self.render_users_state(
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                    feedback={"error": "Kullanıcı eklenirken bir hata oluştu. Bilgileri kontrol edip tekrar deneyin."},
                    form_defaults=defaults,
                )
                return
            role_name = next((row["name"] for row in db.list_roles() if row["code"] == role_code), role_code)
            self.audit("Kullanıcı Eklendi", "Kullanıcılar", user_id, f"{full_name} • Rol: {role_name}")
            self.render_users_state(feedback={"info": "Kullanıcı başarıyla eklendi."})
            return
        elif parsed.path == "/companies":
            name = form_data.get("name", "").strip()
            code = form_data.get("code", "").strip()
            defaults = {"name": name, "code": code}
            if not name or not code:
                self.render_companies_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Firma adı ve kısa kod zorunludur."},
                    form_defaults=defaults,
                )
                return
            try:
                db.create_company(name, code)
            except Exception:
                self.render_companies_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Firma eklenemedi. Ad veya kod zaten kullanılıyor olabilir."},
                    form_defaults=defaults,
                )
                return
            self.audit("Firma Eklendi", "Firmalar", details=f"{name} ({code})")
            self.render_companies_state(feedback={"info": "Firma eklendi."})
            return
        elif parsed.path == "/companies/update":
            item_id = form_data.get("id", "").strip()
            name = form_data.get("name", "").strip()
            code = form_data.get("code", "").strip()
            target = db.get_company_by_id(int(item_id)) if item_id.isdigit() else None
            if not target or not name or not code:
                self.render_companies_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Firma güncelleme bilgileri eksik."},
                    edit_item=target,
                )
                return
            try:
                db.update_company(int(item_id), name, code)
            except Exception:
                self.render_companies_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Firma güncellenemedi. Ad veya kod kullanımda olabilir."},
                    edit_item=target,
                )
                return
            self.audit("Firma Güncellendi", "Firmalar", int(item_id), f"{target['name']} -> {name}")
            self.render_companies_state(feedback={"info": "Firma güncellendi."})
            return
        elif parsed.path == "/companies/delete":
            item_id = form_data.get("id", "").strip()
            target = db.get_company_by_id(int(item_id)) if item_id.isdigit() else None
            if not target:
                self.render_companies_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Silinecek firma bulunamadı."},
                )
                return
            if db.count_users_for_company(int(item_id)) > 0 or db.list_branches(int(item_id)):
                self.render_companies_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Firmaya bağlı kullanıcı veya şubeler var. Önce onları taşıyın ya da silin."},
                )
                return
            db.delete_company(int(item_id))
            self.audit("Firma Silindi", "Firmalar", int(item_id), str(target["name"]))
            self.render_companies_state(feedback={"info": "Firma silindi."})
            return
        elif parsed.path == "/branches":
            company_id_raw = form_data.get("company_id", "").strip()
            name = form_data.get("name", "").strip()
            code = form_data.get("code", "").strip()
            defaults = {"company_id": company_id_raw, "name": name, "code": code}
            company_id = int(company_id_raw) if company_id_raw.isdigit() else None
            if not company_id or not db.get_company_by_id(company_id) or not name or not code:
                self.render_branches_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Şube için firma, ad ve kısa kod zorunludur."},
                    form_defaults=defaults,
                )
                return
            try:
                db.create_branch(company_id, name, code)
            except Exception:
                self.render_branches_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Şube eklenemedi. Kod aynı firma içinde kullanımda olabilir."},
                    form_defaults=defaults,
                )
                return
            self.audit("Şube Eklendi", "Şubeler", details=f"{name} ({code})")
            self.render_branches_state(feedback={"info": "Şube eklendi."})
            return
        elif parsed.path == "/branches/update":
            item_id = form_data.get("id", "").strip()
            company_id_raw = form_data.get("company_id", "").strip()
            name = form_data.get("name", "").strip()
            code = form_data.get("code", "").strip()
            target = db.get_branch_by_id(int(item_id)) if item_id.isdigit() else None
            company_id = int(company_id_raw) if company_id_raw.isdigit() else None
            if not target or not company_id or not db.get_company_by_id(company_id) or not name or not code:
                self.render_branches_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Şube güncelleme bilgileri eksik."},
                    edit_item=target,
                )
                return
            try:
                db.update_branch(int(item_id), company_id, name, code)
            except Exception:
                self.render_branches_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Şube güncellenemedi. Kod aynı firma içinde kullanımda olabilir."},
                    edit_item=target,
                )
                return
            self.audit("Şube Güncellendi", "Şubeler", int(item_id), f"{target['name']} -> {name}")
            self.render_branches_state(feedback={"info": "Şube güncellendi."})
            return
        elif parsed.path == "/branches/delete":
            item_id = form_data.get("id", "").strip()
            target = db.get_branch_by_id(int(item_id)) if item_id.isdigit() else None
            if not target:
                self.render_branches_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Silinecek şube bulunamadı."},
                )
                return
            if db.count_users_for_branch(int(item_id)) > 0:
                self.render_branches_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Bu şubeye bağlı kullanıcılar var. Önce kullanıcı atamalarını değiştirin."},
                )
                return
            db.delete_branch(int(item_id))
            self.audit("Şube Silindi", "Şubeler", int(item_id), str(target["name"]))
            self.render_branches_state(feedback={"info": "Şube silindi."})
            return
        elif parsed.path == "/roles":
            name = form_data.get("name", "").strip()
            description = form_data.get("description", "").strip()
            defaults = {"name": name, "description": description}
            if not name:
                self.render_roles_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Rol adı zorunludur."},
                    form_defaults=defaults,
                )
                return
            role_code = _slugify_role_code(name)
            if not role_code:
                self.render_roles_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Geçerli bir rol adı girin."},
                    form_defaults=defaults,
                )
                return
            if db.get_role_by_code(role_code):
                self.render_roles_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Bu role ait kod zaten var. Farklı bir ad deneyin."},
                    form_defaults=defaults,
                )
                return
            try:
                db.create_role(role_code, name, description)
            except Exception:
                self.render_roles_state(
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                    feedback={"error": "Rol eklenirken bir hata oluştu."},
                    form_defaults=defaults,
                )
                return
            self.audit("Rol Eklendi", "Roller", details=f"{name} ({role_code})")
            self.render_roles_state(feedback={"info": "Rol eklendi."})
            return
        elif parsed.path == "/roles/update":
            code = form_data.get("code", "").strip()
            name = form_data.get("name", "").strip()
            description = form_data.get("description", "").strip()
            target = db.get_role_by_code(code) if code else None
            if not target or code in db.SYSTEM_ROLE_CODES:
                self.render_roles_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Bu rol düzenlenemez."},
                )
                return
            if not name:
                self.render_roles_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Rol adı zorunludur."},
                    edit_item=dict(target),
                )
                return
            try:
                db.update_role(code, name, description)
            except Exception:
                self.render_roles_state(
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                    feedback={"error": "Rol güncellenirken bir hata oluştu."},
                    edit_item=dict(target),
                )
                return
            self.audit("Rol Güncellendi", "Roller", int(target["id"]), f"{target['name']} -> {name}")
            self.render_roles_state(feedback={"info": "Rol güncellendi."})
            return
        elif parsed.path == "/roles/delete":
            code = form_data.get("code", "").strip()
            target = db.get_role_by_code(code) if code else None
            if not target:
                self.render_roles_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Silinecek rol bulunamadı."},
                )
                return
            if code in db.SYSTEM_ROLE_CODES:
                self.render_roles_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Sistem rolleri silinemez."},
                )
                return
            if db.count_users_for_role(code) > 0:
                self.render_roles_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Bu role bağlı kullanıcılar var. Önce kullanıcı rollerini değiştirin."},
                )
                return
            try:
                db.delete_role(code)
            except Exception:
                self.render_roles_state(
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                    feedback={"error": "Rol silinirken bir hata oluştu."},
                )
                return
            self.audit("Rol Silindi", "Roller", int(target["id"]), f"{target['name']} ({code})")
            self.render_roles_state(feedback={"info": "Rol silindi."})
            return
        elif parsed.path == "/users/update":
            user_id = form_data.get("id", "").strip()
            full_name = form_data.get("full_name", "").strip()
            username = form_data.get("username", "").strip()
            email = form_data.get("email", "").strip()
            phone = form_data.get("phone", "").strip()
            password = form_data.get("password", "")
            selected_company_ids = _parse_int_list(parsed_body.get("company_ids", []))
            selected_branch_ids = _parse_int_list(parsed_body.get("branch_ids", []))
            role_code = form_data.get("role_code", "ogretmen").strip()
            is_active = form_data.get("is_active", "1").strip() == "1"
            normalized_company_ids, normalized_branch_ids, relation_error = _normalize_user_company_branch_selection(selected_company_ids, selected_branch_ids)
            company_id = normalized_company_ids[0] if normalized_company_ids else None
            branch_id = normalized_branch_ids[0] if normalized_branch_ids else None
            if relation_error:
                self.render_users_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": relation_error},
                    edit_item=db.get_user_by_id(int(user_id)) if user_id.isdigit() else None,
                )
                return
            if not user_id.isdigit() or not full_name or not username:
                target = db.get_user_by_id(int(user_id)) if user_id.isdigit() else None
                if target:
                    role_codes = ",".join(db.get_user_role_codes(int(user_id)))
                    target = dict(target)
                    target["role_codes"] = role_codes
                self.render_users_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Güncelleme için gerekli alanları doldurun."},
                    edit_item=target,
                )
                return
            if password and len(password) < 6:
                target = db.get_user_by_id(int(user_id))
                if target:
                    role_codes = ",".join(db.get_user_role_codes(int(user_id)))
                    target = dict(target)
                    target["role_codes"] = role_codes
                self.render_users_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Şifre en az 6 karakter olmalı."},
                    edit_item=target,
                )
                return
            existing_username = db.get_user_by_username(username)
            existing_email = db.get_user_by_email(email) if email else None
            if existing_username and existing_username["id"] != int(user_id):
                target = db.get_user_by_id(int(user_id))
                if target:
                    role_codes = ",".join(db.get_user_role_codes(int(user_id)))
                    target = dict(target)
                    target["role_codes"] = role_codes
                self.render_users_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Bu kullanıcı adı zaten kullanılıyor."},
                    edit_item=target,
                )
                return
            if existing_email and existing_email["id"] != int(user_id):
                target = db.get_user_by_id(int(user_id))
                if target:
                    role_codes = ",".join(db.get_user_role_codes(int(user_id)))
                    target = dict(target)
                    target["role_codes"] = role_codes
                self.render_users_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Bu e-posta başka bir kullanıcıda kayıtlı."},
                    edit_item=target,
                )
                return
            try:
                before_user = db.get_user_by_id(int(user_id))
                db.update_user(
                    user_id=int(user_id),
                    username=username,
                    full_name=full_name,
                    email=email,
                    phone=phone,
                    company_id=company_id,
                    company_ids=normalized_company_ids,
                    branch_id=branch_id,
                    branch_ids=normalized_branch_ids,
                    is_active=is_active,
                    role_codes=[role_code],
                    password=password,
                )
            except Exception:
                target = db.get_user_by_id(int(user_id))
                if target:
                    role_codes = ",".join(db.get_user_role_codes(int(user_id)))
                    target = dict(target)
                    target["role_codes"] = role_codes
                self.render_users_state(
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                    feedback={"error": "Kullanıcı güncellenirken bir hata oluştu."},
                    edit_item=target,
                )
                return
            previous_name = before_user["full_name"] if before_user and before_user["full_name"] else (before_user["username"] if before_user else username)
            self.audit("Kullanıcı Güncellendi", "Kullanıcılar", int(user_id), f"{previous_name} -> {full_name}")
            self.render_users_state(feedback={"info": "Kullanıcı bilgileri güncellendi."})
            return
        elif parsed.path == "/users/toggle-active":
            user_id = form_data.get("id", "").strip()
            if user_id.isdigit():
                target_user = db.get_user_by_id(int(user_id))
                if target_user:
                    role_codes = db.get_user_role_codes(int(user_id))
                    if "admin" not in role_codes:
                        db.update_user(
                            user_id=int(user_id),
                            username=target_user["username"],
                            full_name=target_user["full_name"] or "",
                            email=target_user["email"] or "",
                            phone=target_user["phone"] or "",
                            company_id=row_value(target_user, "company_id"),
                            company_ids=db.get_user_company_ids(int(user_id)),
                            branch_id=row_value(target_user, "branch_id"),
                            branch_ids=db.get_user_branch_ids(int(user_id)),
                            is_active=not bool(target_user["is_active"]),
                            role_codes=role_codes,
                            password="",
                        )
                        yeni_durum = "Aktif" if not bool(target_user["is_active"]) else "Pasif"
                        self.audit("Kullanıcı Durumu Değişti", "Kullanıcılar", int(user_id), f"{target_user['full_name'] or target_user['username']} -> {yeni_durum}")
                        self.render_users_state(feedback={"info": "Kullanıcı durumu güncellendi."})
                        return
            self.render_users_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Bu kullanıcı için durum değişikliği yapılamadı."},
            )
            return
        elif parsed.path == "/permissions":
            role_code = form_data.get("role_code", "").strip()
            if not role_code:
                self.render_permissions_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Önce bir rol seçin."},
                )
                return
            permission_codes = parsed_body.get("permission_code", [])
            db.set_role_permissions(role_code, permission_codes)
            role_row = db.get_role_by_code(role_code)
            self.audit(
                "Yetkiler Güncellendi",
                "Yetkiler",
                int(role_row["id"]) if role_row else None,
                f"{role_row['name'] if role_row else role_code} • {len(permission_codes)} izin",
            )
            self.render_permissions_state(
                role_code=role_code,
                feedback={"info": "Rol yetkileri güncellendi."},
            )
            return
        elif parsed.path == "/notification-settings":
            current_user_id = int(self.current_user["id"])
            settings = {
                "badge_pending_requests": 1 if form_data.get("badge_pending_requests", "") == "1" else 0,
                "approval_items": 1 if form_data.get("approval_items", "") == "1" else 0,
                "outgoing_items": 1 if form_data.get("outgoing_items", "") == "1" else 0,
                "task_alerts": 1 if form_data.get("task_alerts", "") == "1" else 0,
                "document_alerts": 1 if form_data.get("document_alerts", "") == "1" else 0,
                "event_reminders": 1 if form_data.get("event_reminders", "") == "1" else 0,
            }
            db.save_notification_settings(current_user_id, settings)
            aktif_sayi = sum(int(value) for value in settings.values())
            self.audit("Bildirim Ayarları Kaydedildi", "Bildirim Ayarları", current_user_id, f"{aktif_sayi} ayar açık")
            self.render_notification_settings_state(feedback={"info": "Bildirim ayarları kaydedildi."})
            return
        elif parsed.path == "/backup-settings/create":
            try:
                backup_path = db.create_backup_now()
            except OSError:
                self.render_backup_settings_state(feedback={"error": "Yedek oluşturulamadı. Dosya izinlerini kontrol edin."})
                return
            self.audit("Manuel Yedek Alındı", "Yedekleme", details=backup_path.name)
            self.redirect("/backup-settings?info=created")
            return
        elif parsed.path == "/file-settings":
            raw_extensions = form_data.get("allowed_extensions", "")
            max_size_raw = form_data.get("max_file_size_mb", "").strip()
            normalized_extensions = _normalize_extension_list(raw_extensions)
            if not normalized_extensions:
                self.render_file_settings_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "En az bir dosya uzantısı tanımlayın."},
                    form_defaults={
                        "allowed_extensions": raw_extensions,
                        "max_file_size_mb": max_size_raw,
                    },
                )
                return
            try:
                max_file_size_mb = max(1, min(int(max_size_raw), 100))
            except ValueError:
                self.render_file_settings_state(
                    status=HTTPStatus.BAD_REQUEST,
                    feedback={"error": "Maksimum boyut için 1 ile 100 arasında bir sayı girin."},
                    form_defaults={
                        "allowed_extensions": raw_extensions,
                        "max_file_size_mb": max_size_raw,
                    },
                )
                return
            db.save_file_settings(normalized_extensions, max_file_size_mb)
            self.audit("Dosya Ayarları Kaydedildi", "Dosya Ayarları", details=f"{normalized_extensions} • {max_file_size_mb} MB")
            self.render_file_settings_state(feedback={"info": "Dosya ayarları kaydedildi."})
            return
        else:
            self.respond(HTTPStatus.NOT_FOUND, not_found_page(self.current_user, self.allowed_paths))
            return

        if parsed.path == "/meetings":
            self.redirect(f"/meetings?meeting={meeting_id}")
        elif parsed.path in {"/tasks/toggle", "/tasks/update", "/tasks/delete", "/tasks/requests/approve", "/tasks/requests/reject"}:
            self.redirect("/tasks")
        elif parsed.path in {"/meetings/update"}:
            self.redirect(f"/meetings?meeting={form_data.get('id', '').strip()}")
        elif parsed.path in {"/meetings/delete"}:
            self.redirect("/meetings")
        elif parsed.path in {"/meeting-templates", "/meeting-templates/delete"}:
            self.redirect("/meeting-templates")
        elif parsed.path in {"/meetings/task"}:
            self.redirect(f"/meetings?meeting={form_data.get('meeting_id', '').strip()}")
        elif parsed.path in {"/documents/update", "/documents/delete", "/documents/toggle"}:
            self.redirect("/documents")
        elif parsed.path in {"/events/update", "/events/delete"}:
            self.redirect("/events")
        elif parsed.path in {"/users", "/users/update", "/users/toggle-active"}:
            self.redirect("/users")
        elif parsed.path in {"/companies", "/companies/update", "/companies/delete"}:
            self.redirect("/companies")
        elif parsed.path in {"/branches", "/branches/update", "/branches/delete"}:
            self.redirect("/branches")
        elif parsed.path in {"/roles", "/roles/update", "/roles/delete"}:
            self.redirect("/roles")
        elif parsed.path in {"/notification-settings"}:
            self.redirect("/notification-settings")
        elif parsed.path in {"/backup-settings/create"}:
            self.redirect("/backup-settings")
        elif parsed.path in {"/file-settings"}:
            self.redirect("/file-settings")
        elif parsed.path in {"/permissions"}:
            self.redirect("/permissions")
        elif parsed.path in {"/suppliers/update"}:
            self.redirect(f"/suppliers?supplier={form_data.get('id', '').strip()}")
        elif parsed.path in {"/supplier-notes", "/supplier-notes/update", "/supplier-notes/delete"}:
            self.redirect(f"/suppliers?supplier={form_data.get('supplier_id', '').strip()}")
        else:
            self.redirect(parsed.path)

    def dashboard(self) -> None:
        current_user_id = int(self.current_user["id"])
        perms = self.current_permissions
        is_admin = "admin" in db.get_user_role_codes(current_user_id)
        mv = {
            "tasks": "tasks.view" in perms,
            "documents": "documents.view" in perms,
            "meetings": "meetings.view" in perms,
            "events": "events.view" in perms,
            "suppliers": "suppliers.view" in perms,
        }

        summary = {
            "pending_tasks": 0,
            "upcoming_documents": 0,
            "meeting_count": 0,
            "supplier_count": 0,
            "event_count": 0,
        }
        tasks = []
        documents = []
        meetings = []
        suppliers = []
        events = []

        if mv["tasks"]:
            visible_active_tasks = db.fetch_all(*_build_tasks_query("all", current_user_id, is_admin))
            summary["pending_tasks"] = len(visible_active_tasks)
            tasks = visible_active_tasks[:5]

        if mv["documents"]:
            active_document_items, _ = _build_document_items(current_user_id, is_admin)
            upcoming_document_items = _filter_document_items(active_document_items, ["upcoming"])
            summary["upcoming_documents"] = len(upcoming_document_items)
            documents = upcoming_document_items[:5]

        if mv["meetings"]:
            summary["meeting_count"] = db.fetch_one("SELECT COUNT(*) AS count FROM meeting_notes")["count"]
            meetings = db.fetch_all("SELECT * FROM meeting_notes ORDER BY meeting_date DESC LIMIT 5")

        if mv["suppliers"]:
            summary["supplier_count"] = db.fetch_one("SELECT COUNT(*) AS count FROM suppliers")["count"]
            suppliers = db.fetch_all("SELECT * FROM suppliers ORDER BY next_contact_at ASC LIMIT 5")

        if mv["events"]:
            summary["event_count"] = db.fetch_one(
                "SELECT COUNT(*) AS count FROM events "
                "WHERE COALESCE(NULLIF(end_date, ''), event_date) >= date('now', 'localtime')"
            )["count"]
            events = db.fetch_all(
                "SELECT * FROM events "
                "WHERE COALESCE(NULLIF(end_date, ''), event_date) >= date('now', 'localtime') "
                "ORDER BY event_date ASC LIMIT 5"
            )

        alerts = _build_dashboard_alerts(current_user_id, is_admin, perms)
        self.respond(
            HTTPStatus.OK,
            dashboard_page(
                summary,
                tasks,
                documents,
                meetings,
                suppliers,
                events,
                alerts,
                mv,
                self.current_user,
                self.allowed_paths,
                theme="light",
            ),
        )

    def notifications_page(self) -> None:
        current_user_id = int(self.current_user["id"])
        is_admin = "admin" in db.get_user_role_codes(current_user_id)
        groups = _build_notification_groups(current_user_id, is_admin, self.current_permissions)
        total_count = sum(len(group.get("items", [])) for group in groups)
        self.respond(HTTPStatus.OK, notifications_page(groups, total_count, self.current_user, self.allowed_paths, theme="light"))

    def search_page(self, query: dict[str, list[str]]) -> None:
        raw_query = query.get("q", [""])[0].strip()
        groups: list[dict] = []
        perms = self.current_permissions
        if raw_query:
            like = f"%{raw_query}%"
            groups = []
            if "tasks.view" in perms:
                task_rows = db.fetch_all(
                    "SELECT id, title, due_date FROM tasks "
                    "WHERE title LIKE ? OR description LIKE ? OR responsible_person LIKE ? "
                    "ORDER BY updated_at DESC LIMIT 8",
                    (like, like, like),
                )
                groups.append(
                    {
                        "title": "Görevler",
                        "items": [
                            {"href": "/tasks", "title": row["title"], "meta": f"Termin: {row['due_date'] or '-'}"}
                            for row in task_rows
                        ],
                    }
                )
            if "documents.view" in perms:
                document_rows = db.fetch_all(
                    "SELECT id, title, due_date FROM documents "
                    "WHERE title LIKE ? OR description LIKE ? "
                    "ORDER BY updated_at DESC LIMIT 8",
                    (like, like),
                )
                groups.append(
                    {
                        "title": "Evraklar",
                        "items": [
                            {"href": "/documents", "title": row["title"], "meta": f"Tarih: {row['due_date'] or '-'}"}
                            for row in document_rows
                        ],
                    }
                )
            if "meetings.view" in perms:
                meeting_rows = db.fetch_all(
                    "SELECT id, title, meeting_date, agenda, notes, decisions FROM meeting_notes "
                    "WHERE title LIKE ? OR agenda LIKE ? OR notes LIKE ? OR decisions LIKE ? "
                    "ORDER BY meeting_date DESC LIMIT 8",
                    (like, like, like, like),
                )
                groups.append(
                    {
                        "title": "Toplantılar",
                        "items": [
                            {"href": f"/meetings?meeting={row['id']}", "title": row["title"], "meta": f"Tarih: {row['meeting_date'] or '-'}"}
                            for row in meeting_rows
                        ],
                    }
                )
            if "events.view" in perms:
                event_rows = db.fetch_all(
                    "SELECT id, title, event_date, end_date, level FROM events "
                    "WHERE title LIKE ? OR notes LIKE ? OR level LIKE ? "
                    "ORDER BY event_date ASC LIMIT 8",
                    (like, like, like),
                )
                groups.append(
                    {
                        "title": "Etkinlikler",
                        "items": [
                            {"href": "/events", "title": row["title"], "meta": f"{_format_date_range(row['event_date'], row['end_date'])} · {row['level'] or '-'}"}
                            for row in event_rows
                        ],
                    }
                )
            if "suppliers.view" in perms:
                supplier_rows = db.fetch_all(
                    "SELECT id, company_name, contact_name, service_type FROM suppliers "
                    "WHERE company_name LIKE ? OR contact_name LIKE ? OR service_type LIKE ? "
                    "ORDER BY company_name ASC LIMIT 8",
                    (like, like, like),
                )
                groups.append(
                    {
                        "title": "Tedarikçiler",
                        "items": [
                            {"href": f"/suppliers?supplier={row['id']}", "title": row["company_name"], "meta": f"{row['contact_name'] or '-'} · {row['service_type'] or '-'}"}
                            for row in supplier_rows
                        ],
                    }
                )
            groups = [group for group in groups if group["items"]]
        self.respond(HTTPStatus.OK, search_results_page(raw_query, groups, self.current_user, self.allowed_paths))

    def tasks_page(self, query: dict[str, list[str]]) -> None:
        active_filter = query.get("filter", ["all"])[0]
        current_user_id = int(self.current_user["id"])
        is_admin = "admin" in db.get_user_role_codes(current_user_id)
        share_users = [user for user in db.list_active_users() if int(user["id"]) != current_user_id]
        share_roles = db.list_roles()
        active_user_map = {
            int(user["id"]): (user["full_name"] or user["username"] or "Kullanıcı")
            for user in db.list_active_users()
        }
        role_map = {int(role["id"]): (role["name"] or role["code"] or "Rol") for role in share_roles}
        active_items = db.fetch_all(*_build_tasks_query(active_filter, current_user_id, is_admin))
        completed_items = db.fetch_all(*_build_completed_tasks_query(current_user_id, is_admin))
        filter_counts = {
            "all": len(db.fetch_all(*_build_tasks_query("all", current_user_id, is_admin))),
            "today": len(db.fetch_all(*_build_tasks_query("today", current_user_id, is_admin))),
            "upcoming": len(db.fetch_all(*_build_tasks_query("upcoming", current_user_id, is_admin))),
            "overdue": len(db.fetch_all(*_build_tasks_query("overdue", current_user_id, is_admin))),
            "no_date": len(db.fetch_all(*_build_tasks_query("no_date", current_user_id, is_admin))),
        }
        edit_item = None
        edit_values = query.get("edit", [])
        if edit_values and edit_values[0].isdigit():
            all_visible_items = list(active_items) + list(completed_items)
            selected_id = int(edit_values[0])
            found_item = next((item for item in all_visible_items if int(item["id"]) == selected_id), None)
            if found_item:
                edit_item = dict(found_item)
                edit_item["_share_user_ids"] = db.get_record_user_share_ids("tasks", selected_id)
                edit_item["_share_role_ids"] = db.get_record_role_share_ids("tasks", selected_id)
        active_items = [_attach_task_share_summary(item, active_user_map, role_map, current_user_id) for item in active_items]
        completed_items = [_attach_task_share_summary(item, active_user_map, role_map, current_user_id) for item in completed_items]
        if edit_item:
            edit_item = _attach_task_share_summary(edit_item, active_user_map, role_map, current_user_id)
        can_manage_edit_directly = _can_manage_task_directly(edit_item, current_user_id, is_admin) if edit_item else True
        owner_requests = [_format_task_change_request(row, active_user_map) for row in db.list_pending_task_change_requests(current_user_id)]
        outgoing_request_rows = db.list_outgoing_pending_task_change_requests(current_user_id)
        outgoing_request_map = _build_outgoing_task_request_map(outgoing_request_rows, active_user_map)
        request_history = [_format_task_change_history(row, current_user_id, active_user_map) for row in db.list_task_change_history_for_user(current_user_id)]
        active_items = [_attach_task_request_state(item, outgoing_request_map) for item in active_items]
        completed_items = [_attach_task_request_state(item, outgoing_request_map) for item in completed_items]
        if edit_item:
            edit_item = _attach_task_request_state(edit_item, outgoing_request_map)
        feedback = _build_task_feedback(query)
        activity_view = query.get("activity", ["week"])[0].strip().lower()
        self.respond(HTTPStatus.OK, tasks_page(active_items, completed_items, share_users, share_roles, owner_requests, request_history, edit_item, can_manage_edit_directly, active_filter, filter_counts, feedback, self.current_user, self.allowed_paths, activity_view))

    def meetings_page(self, query: dict[str, list[str]]) -> None:
        active_tab = query.get("tab", ["notes"])[0]
        items = db.fetch_all("SELECT * FROM meeting_notes ORDER BY meeting_date DESC, id DESC")
        attachment_count_map = db.get_attachment_count_map("meetings", [int(item["id"]) for item in items])
        items = [dict(item) for item in items]
        for item in items:
            item["_attachment_count"] = attachment_count_map.get(int(item["id"]), 0)
        templates = db.fetch_all("SELECT * FROM meeting_templates ORDER BY sort_order ASC, title ASC")
        file_settings = db.get_file_settings()
        selected_item = None
        meeting_id = query.get("meeting", [""])[0]
        if meeting_id.isdigit():
            selected_item = db.fetch_one("SELECT * FROM meeting_notes WHERE id = ?", (int(meeting_id),))
            if selected_item:
                linked_tasks = db.fetch_all(
                    "SELECT title FROM tasks WHERE related_type = 'meeting' AND related_id = ?",
                    (int(meeting_id),),
                )
                selected_item = dict(selected_item)
                selected_item["_linked_task_titles"] = {row["title"] for row in linked_tasks}
                selected_item["_attachments"] = [dict(row) for row in db.list_attachments("meetings", int(meeting_id))]
                selected_item["_file_settings"] = db.get_file_settings()
        edit_item = None
        edit_id = query.get("edit", [""])[0]
        if edit_id.isdigit():
            edit_item = db.fetch_one("SELECT * FROM meeting_notes WHERE id = ?", (int(edit_id),))
        show_new = query.get("new", [""])[0] == "1"
        feedback = {
            "info": _first_feedback_value(query.get("info", []), {
                "meeting_saved": "Toplantı kaydedildi.",
                "meeting_saved_with_attachment": "Toplantı kaydedildi, dosya eklendi.",
                "meeting_updated": "Toplantı güncellendi.",
                "meeting_deleted": "Toplantı silindi.",
                "attachment_uploaded": "Dosya eklendi.",
                "attachment_deleted": "Dosya silindi.",
            }),
            "error": _first_feedback_value(query.get("error", []), {
                "attachment_missing": "Dosya seçmeden gönderim yapılamaz.",
                "attachment_invalid_type": "Bu uzantı için dosya yükleme izni yok.",
                "attachment_too_large": "Dosya boyutu izin verilen sınırı aşıyor.",
            }),
        }
        page = meetings_dashboard_page(items, selected_item, templates, active_tab, edit_item, show_new, self.current_user, self.allowed_paths, feedback, file_settings)
        self.respond(HTTPStatus.OK, page)

    def documents_page(self, query: dict[str, list[str]]) -> None:
        active_filters = [value for value in query.get("filter", []) if value in {"today", "upcoming", "overdue", "recurring"}]
        current_user_id = int(self.current_user["id"])
        is_admin = "admin" in db.get_user_role_codes(current_user_id)
        feedback = _build_document_feedback(query)
        file_settings = db.get_file_settings()
        active_user_map = {
            int(user["id"]): (user["full_name"] or user["username"] or "Kullanıcı")
            for user in db.list_active_users()
        }
        share_users = [user for user in db.list_active_users() if int(user["id"]) != current_user_id]
        share_roles = db.list_roles()
        role_map = {int(role["id"]): (role["name"] or role["code"] or "Rol") for role in share_roles}
        active_items, completed_items = _build_document_items(current_user_id, is_admin)
        owner_requests = [_format_document_change_request(row, active_user_map) for row in db.list_pending_document_change_requests(current_user_id)]
        outgoing_request_rows = db.list_outgoing_pending_document_change_requests(current_user_id)
        outgoing_request_map = _build_outgoing_document_request_map(outgoing_request_rows, active_user_map)
        active_items = [_attach_document_share_summary(item, active_user_map, role_map, current_user_id) for item in active_items]
        active_items = [_attach_document_request_state(item, outgoing_request_map) for item in active_items]
        completed_items = [_attach_document_share_summary(item, active_user_map, role_map, current_user_id) for item in completed_items]
        completed_items = [_attach_document_request_state(item, outgoing_request_map) for item in completed_items]
        all_items_for_counts = active_items + completed_items
        one_time_counts = db.get_attachment_count_map("documents", [int(item["id"]) for item in all_items_for_counts if row_value(item, "kind") == "one_time"])
        recurring_counts = db.get_attachment_count_map("recurring_documents", [int(item["id"]) for item in all_items_for_counts if row_value(item, "kind") == "recurring"])

        def attach_document_file_meta(item):
            row = dict(item)
            module_name = "recurring_documents" if row_value(row, "kind") == "recurring" else "documents"
            count_map = recurring_counts if module_name == "recurring_documents" else one_time_counts
            row["_attachment_count"] = count_map.get(int(row["id"]), 0)
            return row

        active_items = [attach_document_file_meta(item) for item in active_items]
        completed_items = [attach_document_file_meta(item) for item in completed_items]
        filtered_items = _filter_document_items(active_items, active_filters)
        filter_counts = {
            "all": len(active_items),
            "today": len(_filter_document_items(active_items, ["today"])),
            "upcoming": len(_filter_document_items(active_items, ["upcoming"])),
            "overdue": len(_filter_document_items(active_items, ["overdue"])),
            "recurring": len([item for item in active_items if item["kind"] == "recurring"]),
        }
        edit_item = None
        edit_kind = query.get("edit_kind", [""])[0]
        edit_id = query.get("edit_id", [""])[0]
        if edit_id.isdigit() and edit_kind in {"one_time", "recurring"}:
            all_items = active_items + completed_items
            edit_item = next((item for item in all_items if item["kind"] == edit_kind and item["id"] == int(edit_id)), None)
        edit_can_manage_directly = True
        if edit_item:
            edit_can_manage_directly = _can_manage_document_directly(edit_item, current_user_id, is_admin)
            attachment_module = "recurring_documents" if edit_kind == "recurring" else "documents"
            edit_item = dict(edit_item)
            edit_item = _attach_document_share_summary(edit_item, active_user_map, role_map, current_user_id)
            edit_item["_attachments"] = [dict(row) for row in db.list_attachments(attachment_module, int(edit_id))]
            edit_item["_file_settings"] = file_settings
        request_history = [
            _format_document_change_history(row, current_user_id, active_user_map)
            for row in db.list_document_change_history_for_user(current_user_id, limit=8)
        ]
        page = documents_dashboard_page_filtered(filtered_items, completed_items, quick_document_form(share_users, share_roles, file_settings), edit_item, active_filters, filter_counts, self.current_user, self.allowed_paths, share_users, share_roles, owner_requests, request_history, edit_can_manage_directly, feedback, file_settings)
        self.respond(HTTPStatus.OK, page)

    def events_page(self, query: dict[str, list[str]]) -> None:
        active_levels = [level for level in query.get("level", []) if level in {"Anasınıfı", "İlkokul", "Ortaokul", "Lise"}]
        active_view = query.get("view", ["month"])[0]
        month_param = query.get("month", [""])[0]
        items = db.fetch_all(
            "SELECT * FROM events ORDER BY event_date ASC, title ASC"
        )
        level_counts = {
            "all": len(items),
            "Anasınıfı": len([item for item in items if "Anasınıfı" in _split_event_levels(item["level"])]),
            "İlkokul": len([item for item in items if "İlkokul" in _split_event_levels(item["level"])]),
            "Ortaokul": len([item for item in items if "Ortaokul" in _split_event_levels(item["level"])]),
            "Lise": len([item for item in items if "Lise" in _split_event_levels(item["level"])]),
        }
        if active_levels:
            items = [
                item for item in items
                if any(level in _split_event_levels(item["level"]) for level in active_levels)
            ]
        edit_item = None
        edit_id = query.get("edit", [""])[0]
        if edit_id.isdigit():
            edit_item = db.fetch_one("SELECT * FROM events WHERE id = ?", (int(edit_id),))
        today = datetime.now()
        if month_param:
            try:
                ref_date = datetime.strptime(month_param + "-01", "%Y-%m-%d")
            except ValueError:
                ref_date = today
        else:
            ref_date = today
        date_map: dict[str, list[dict[str, str]]] = {}
        for item in items:
            for day_key in _iter_event_days(item["event_date"], item["end_date"]):
                date_map.setdefault(day_key, []).append(
                    {
                        "title": item["title"],
                        "level_label": format_event_levels(item["level"]),
                        "time_range": item["time_range"] if "time_range" in item.keys() else "",
                        "notes": item["notes"] if "notes" in item.keys() else "",
                        "is_holiday": False,
                    }
                )
        _merge_public_holidays(date_map, ref_date.year)
        if active_view == "year":
            month_label, calendar_html = render_event_year_calendar(ref_date.year, date_map, active_levels)
        else:
            month_label, calendar_html = render_event_calendar(ref_date.year, ref_date.month, date_map)
        prev_date = _add_month_delta(ref_date, -1)
        next_date = _add_month_delta(ref_date, 1)
        level_suffix = "".join(f"&level={level}" for level in active_levels)
        view_suffix = "" if active_view == "month" else f"&view={active_view}"
        prev_href = f"/events?month={prev_date.strftime('%Y-%m')}{level_suffix}{view_suffix}"
        next_href = f"/events?month={next_date.strftime('%Y-%m')}{level_suffix}{view_suffix}"
        today_params = []
        if active_view != "month":
            today_params.append(f"view={active_view}")
        today_params.extend(f"level={level}" for level in active_levels)
        today_href = "/events" if not today_params else "/events?" + "&".join(today_params)
        self.respond(
            HTTPStatus.OK,
            events_page(
                items,
                quick_event_form(),
                active_levels,
                level_counts,
                active_view,
                month_label,
                calendar_html,
                calendar_nav_bar(prev_href, next_href, today_href),
                edit_item,
                self.current_user,
                self.allowed_paths,
            ),
        )

    def suppliers_page(self, query: dict[str, list[str]]) -> None:
        _cleanup_supplier_phone()
        items = db.fetch_all("SELECT * FROM suppliers ORDER BY company_name ASC")
        selected_supplier = None
        selected_id = query.get("supplier", [""])[0]
        show_note_form = query.get("add_note", [""])[0] == "1"
        if selected_id.isdigit():
            selected_supplier = db.fetch_one("SELECT * FROM suppliers WHERE id = ?", (int(selected_id),))
        elif items:
            selected_supplier = items[0]
        notes = []
        note_edit = None
        if selected_supplier:
            notes = db.fetch_all(
                "SELECT * FROM supplier_interactions WHERE supplier_id = ? ORDER BY interaction_date DESC, id DESC",
                (selected_supplier["id"],),
            )
            note_edit_id = query.get("note_edit", [""])[0]
            if note_edit_id.isdigit():
                note_edit = db.fetch_one(
                    "SELECT * FROM supplier_interactions WHERE id = ? AND supplier_id = ?",
                    (int(note_edit_id), selected_supplier["id"]),
                )
        edit_item = None
        edit_id = query.get("edit", [""])[0]
        if edit_id.isdigit():
            edit_item = db.fetch_one("SELECT * FROM suppliers WHERE id = ?", (int(edit_id),))
        page = suppliers_dashboard_page(items, selected_supplier, notes, edit_item, note_edit, show_note_form, self.current_user, self.allowed_paths)
        self.respond(HTTPStatus.OK, page)

    def users_page(self, query: dict[str, list[str]]) -> None:
        items = db.list_users()
        roles = db.list_roles()
        companies = db.list_companies()
        branches = db.list_branches()
        edit_item = None
        feedback = _build_user_feedback(query)
        edit_id = query.get("edit", [""])[0]
        if edit_id.isdigit():
            edit_item = db.get_user_by_id(int(edit_id))
            if edit_item:
                role_codes = ",".join(db.get_user_role_codes(int(edit_id)))
                edit_item = dict(edit_item)
                edit_item["role_codes"] = role_codes
        page = users_page(items, roles, companies, branches, edit_item, self.current_user, self.allowed_paths, feedback)
        self.respond(HTTPStatus.OK, page)

    def companies_page(self, query: dict[str, list[str]]) -> None:
        items = []
        for row in db.list_companies():
            item = dict(row)
            item["branch_count"] = len(db.list_branches(int(row["id"])))
            item["user_count"] = db.count_users_for_company(int(row["id"]))
            items.append(item)
        feedback = _build_company_feedback(query)
        edit_item = None
        edit_id = query.get("edit", [""])[0]
        if edit_id.isdigit():
            edit_item = db.get_company_by_id(int(edit_id))
        page = companies_page(items, edit_item, self.current_user, self.allowed_paths, feedback)
        self.respond(HTTPStatus.OK, page)

    def branches_page(self, query: dict[str, list[str]]) -> None:
        companies = db.list_companies()
        company_lookup = {int(row["id"]): row["name"] for row in companies}
        items = []
        for row in db.list_branches():
            item = dict(row)
            item["company_name"] = company_lookup.get(int(row["company_id"]), item.get("company_name", ""))
            item["user_count"] = db.count_users_for_branch(int(row["id"]))
            items.append(item)
        feedback = _build_branch_feedback(query)
        edit_item = None
        edit_id = query.get("edit", [""])[0]
        if edit_id.isdigit():
            edit_item = db.get_branch_by_id(int(edit_id))
        page = branches_page(items, companies, edit_item, self.current_user, self.allowed_paths, feedback)
        self.respond(HTTPStatus.OK, page)

    def roles_page(self, query: dict[str, list[str]]) -> None:
        items = db.list_roles()
        items = [_decorate_role_row(row) for row in items]
        feedback = _build_roles_feedback(query)
        edit_item = None
        edit_code = query.get("edit", [""])[0]
        if edit_code:
            edit_item = db.get_role_by_code(edit_code)
            if edit_item:
                edit_item = _decorate_role_row(edit_item)
        page = roles_page(items, edit_item, self.current_user, self.allowed_paths, feedback)
        self.respond(HTTPStatus.OK, page)

    def permissions_page(self, query: dict[str, list[str]]) -> None:
        roles = db.list_roles()
        permissions = db.list_permissions()
        selected_role_code = query.get("role", [""])[0] or (roles[0]["code"] if roles else "")
        selected_permission_codes = set(db.get_role_permission_codes(selected_role_code)) if selected_role_code else set()
        feedback = _build_permission_feedback(query)
        page = permissions_page(
            roles,
            permissions,
            selected_role_code,
            selected_permission_codes,
            self.current_user,
            self.allowed_paths,
            feedback,
        )
        self.respond(HTTPStatus.OK, page)

    def notification_settings_page(self, query: dict[str, list[str]]) -> None:
        settings = db.get_notification_settings(int(self.current_user["id"]))
        feedback = _build_notification_settings_feedback(query)
        page = notification_settings_page(settings, self.current_user, self.allowed_paths, feedback)
        self.respond(HTTPStatus.OK, page)

    def backup_settings_page(self, query: dict[str, list[str]]) -> None:
        feedback = _build_backup_settings_feedback(query)
        self.render_backup_settings_state(feedback=feedback)

    def file_settings_page(self, query: dict[str, list[str]]) -> None:
        feedback = _build_file_settings_feedback(query)
        self.render_file_settings_state(feedback=feedback)

    def audit_logs_page(self, query: dict[str, list[str]]) -> None:
        feedback = _build_audit_logs_feedback(query)
        filters = {
            "q": query.get("q", [""])[0].strip(),
            "module": query.get("module", [""])[0].strip(),
            "actor": query.get("actor", [""])[0].strip(),
            "action": query.get("action", [""])[0].strip(),
            "date_from": query.get("date_from", [""])[0].strip(),
            "date_to": query.get("date_to", [""])[0].strip(),
        }
        self.render_audit_logs_state(feedback=feedback, filters=filters)

    def export_audit_logs(self, query: dict[str, list[str]]) -> None:
        filters = {
            "q": query.get("q", [""])[0].strip(),
            "module": query.get("module", [""])[0].strip(),
            "actor": query.get("actor", [""])[0].strip(),
            "action": query.get("action", [""])[0].strip(),
            "date_from": query.get("date_from", [""])[0].strip(),
            "date_to": query.get("date_to", [""])[0].strip(),
        }
        items = db.list_audit_logs(
            limit=5000,
            search=filters.get("q", ""),
            date_from=filters.get("date_from", ""),
            date_to=filters.get("date_to", ""),
            module_name=filters.get("module", ""),
            actor_name=filters.get("actor", ""),
            action=filters.get("action", ""),
        )
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["Tarih", "Kullanıcı", "Modül", "İşlem", "Detay"])
        for item in items:
            writer.writerow([
                format_datetime(row_value(item, "created_at") or ""),
                row_value(item, "actor_name") or "Sistem",
                row_value(item, "module_name") or "",
                row_value(item, "action") or "",
                row_value(item, "details") or "",
            ])
        payload = buffer.getvalue().encode("utf-8-sig")
        file_name = f"audit_logs_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.csv"
        headers = [("Content-Disposition", f'attachment; filename="{file_name}"')]
        self.respond(HTTPStatus.OK, payload, content_type="text/csv; charset=utf-8", extra_headers=headers)

    def meeting_templates_page(self, query: dict[str, list[str]]) -> None:
        templates = db.fetch_all("SELECT * FROM meeting_templates ORDER BY sort_order ASC, title ASC")
        feedback = _build_meeting_template_feedback(query)
        page = meeting_templates_page(templates, self.current_user, self.allowed_paths, feedback)
        self.respond(HTTPStatus.OK, page)

    def render_users_state(
        self,
        *,
        status: HTTPStatus = HTTPStatus.OK,
        feedback: dict[str, str] | None = None,
        edit_item=None,
        form_defaults: dict[str, str] | None = None,
    ) -> None:
        items = db.list_users()
        roles = db.list_roles()
        companies = db.list_companies()
        branches = db.list_branches()
        page = users_page(
            items,
            roles,
            companies,
            branches,
            edit_item,
            self.current_user,
            self.allowed_paths,
            feedback or {},
            form_defaults or {},
        )
        self.respond(status, page)

    def render_companies_state(
        self,
        *,
        status: HTTPStatus = HTTPStatus.OK,
        feedback: dict[str, str] | None = None,
        edit_item=None,
        form_defaults: dict[str, str] | None = None,
    ) -> None:
        items = []
        for row in db.list_companies():
            item = dict(row)
            item["branch_count"] = len(db.list_branches(int(row["id"])))
            item["user_count"] = db.count_users_for_company(int(row["id"]))
            items.append(item)
        page = companies_page(items, edit_item, self.current_user, self.allowed_paths, feedback or {}, form_defaults or {})
        self.respond(status, page)

    def render_branches_state(
        self,
        *,
        status: HTTPStatus = HTTPStatus.OK,
        feedback: dict[str, str] | None = None,
        edit_item=None,
        form_defaults: dict[str, str] | None = None,
    ) -> None:
        companies = db.list_companies()
        company_lookup = {int(row["id"]): row["name"] for row in companies}
        items = []
        for row in db.list_branches():
            item = dict(row)
            item["company_name"] = company_lookup.get(int(row["company_id"]), item.get("company_name", ""))
            item["user_count"] = db.count_users_for_branch(int(row["id"]))
            items.append(item)
        page = branches_page(items, companies, edit_item, self.current_user, self.allowed_paths, feedback or {}, form_defaults or {})
        self.respond(status, page)

    def render_roles_state(
        self,
        *,
        status: HTTPStatus = HTTPStatus.OK,
        feedback: dict[str, str] | None = None,
        edit_item=None,
        form_defaults: dict[str, str] | None = None,
    ) -> None:
        items = db.list_roles()
        items = [_decorate_role_row(row) for row in items]
        page = roles_page(
            items,
            _decorate_role_row(edit_item) if edit_item else None,
            self.current_user,
            self.allowed_paths,
            feedback or {},
            form_defaults or {},
        )
        self.respond(status, page)

    def render_permissions_state(
        self,
        *,
        status: HTTPStatus = HTTPStatus.OK,
        role_code: str = "",
        feedback: dict[str, str] | None = None,
    ) -> None:
        roles = db.list_roles()
        permissions = db.list_permissions()
        selected_role_code = role_code or (roles[0]["code"] if roles else "")
        selected_permission_codes = set(db.get_role_permission_codes(selected_role_code)) if selected_role_code else set()
        page = permissions_page(
            roles,
            permissions,
            selected_role_code,
            selected_permission_codes,
            self.current_user,
            self.allowed_paths,
            feedback or {},
        )
        self.respond(status, page)

    def render_notification_settings_state(
        self,
        *,
        status: HTTPStatus = HTTPStatus.OK,
        feedback: dict[str, str] | None = None,
    ) -> None:
        settings = db.get_notification_settings(int(self.current_user["id"]))
        page = notification_settings_page(
            settings,
            self.current_user,
            self.allowed_paths,
            feedback or {},
        )
        self.respond(status, page)

    def render_backup_settings_state(
        self,
        *,
        status: HTTPStatus = HTTPStatus.OK,
        feedback: dict[str, str] | None = None,
    ) -> None:
        backups = []
        for item in db.list_backups():
            backup = dict(item)
            backup["size_label"] = _format_file_size(int(backup.get("size_bytes", 0)))
            backups.append(backup)
        summary = {
            "db_name": db.DB_PATH.name,
            "db_meta": str(db.DB_PATH.parent),
            "backup_dir_name": db.BACKUP_DIR.name,
            "backup_dir_meta": str(db.BACKUP_DIR),
            "uploads_name": "Yükleme klasörü",
            "uploads_meta": str(UPLOADS_DIR),
        }
        page = backup_settings_page(
            backups,
            summary,
            self.current_user,
            self.allowed_paths,
            feedback or {},
        )
        self.respond(status, page)

    def render_file_settings_state(
        self,
        *,
        status: HTTPStatus = HTTPStatus.OK,
        feedback: dict[str, str] | None = None,
        form_defaults: dict[str, str] | None = None,
    ) -> None:
        settings = db.get_file_settings()
        if form_defaults:
            settings = {
                "allowed_extensions": form_defaults.get("allowed_extensions", settings.get("allowed_extensions", "")),
                "max_file_size_mb": form_defaults.get("max_file_size_mb", settings.get("max_file_size_mb", 10)),
            }
        allowed_extensions = str(settings.get("allowed_extensions", ""))
        max_size_value = str(settings.get("max_file_size_mb", 10))
        summary = {
            "uploads_name": "Toplantı Yüklemeleri",
            "uploads_meta": str(UPLOADS_DIR / "meetings"),
            "extensions_name": _format_extension_preview(allowed_extensions),
            "extensions_meta": allowed_extensions,
            "max_size_name": f"{max_size_value} MB",
            "max_size_meta": "Tek dosya için üst sınır",
        }
        page = file_settings_page(
            settings,
            summary,
            self.current_user,
            self.allowed_paths,
            feedback or {},
        )
        self.respond(status, page)

    def render_audit_logs_state(
        self,
        *,
        status: HTTPStatus = HTTPStatus.OK,
        feedback: dict[str, str] | None = None,
        filters: dict[str, str] | None = None,
    ) -> None:
        filters = filters or {}
        items = db.list_audit_logs(
            search=filters.get("q", ""),
            date_from=filters.get("date_from", ""),
            date_to=filters.get("date_to", ""),
            module_name=filters.get("module", ""),
            actor_name=filters.get("actor", ""),
            action=filters.get("action", ""),
        )
        page = audit_logs_page(
            items,
            filters,
            db.list_audit_modules(),
            db.list_audit_users(),
            db.list_audit_actions(),
            self.current_user,
            self.allowed_paths,
            feedback or {},
        )
        self.respond(status, page)

    def serve_static(self, request_path: str) -> None:
        self._serve_file(STATIC_DIR, request_path.removeprefix("/static/"))

    def serve_assets(self, request_path: str) -> None:
        self._serve_file(ASSETS_DIR, request_path.removeprefix("/assets/"))

    def _serve_file(self, base_dir: Path, relative_path: str) -> None:
        file_path = base_dir / relative_path
        if not file_path.exists() or not file_path.is_file():
            self.respond(HTTPStatus.NOT_FOUND, b"Not found", content_type="text/plain; charset=utf-8")
            return
        mime_type, _ = mimetypes.guess_type(str(file_path))
        self.respond(
            HTTPStatus.OK,
            file_path.read_bytes(),
            content_type=mime_type or "application/octet-stream",
        )

    def _save_uploaded_file(self, module_name: str, record_id: int, upload: dict) -> bool:
        """Yüklenen dosyayı fiziksel olarak kaydeder ve veritabanına ekler."""
        if not (upload and upload.get("filename") and upload.get("content")):
            return False
            
        target_dir = UPLOADS_DIR / module_name / str(record_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        
        safe_name = _sanitize_filename(upload["filename"])
        stored_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}_{safe_name}"
        target_path = target_dir / stored_name
        
        try:
            target_path.write_bytes(upload["content"])
            mime_type = upload.get("content_type") or mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
            db.add_attachment(
                module_name,
                int(record_id),
                upload["filename"],
                stored_name,
                str(target_path),
                mime_type,
                len(upload["content"]),
                int(self.current_user["id"]),
            )
            return True
        except Exception:
            return False

    # --- POST Handlers (Dispatcher tarafından çağrılan metodlar) ---

    def _handle_task_create(self, form_data: dict, parsed_body: dict) -> None:
        user_id = int(self.current_user["id"])
        share_user_ids = _normalize_share_user_ids(parsed_body.get("share_user_ids", []), user_id)
        share_role_ids = _normalize_share_role_ids(parsed_body.get("share_role_ids", []))
        visibility_type = "shared" if share_user_ids or share_role_ids else "private"
        title = form_data.get("title", "").strip()
        task_id = db.execute_insert(
            "INSERT INTO tasks (title, responsible_person, description, category, priority, status, due_date, owner_user_id, visibility_type, created_by, updated_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (title, form_data.get("responsible_person", "").strip(), form_data.get("description", "").strip(), "Genel", form_data.get("priority", "medium"), "pending", form_data.get("due_date", "").strip(), user_id, visibility_type, user_id, user_id),
        )
        db.replace_record_user_shares("tasks", task_id, share_user_ids)
        db.replace_record_role_shares("tasks", task_id, share_role_ids)
        self.audit("Görev Eklendi", "Görevler", task_id, title)
        self.redirect("/tasks")

    def _handle_task_toggle(self, form_data: dict) -> None:
        task_id = form_data.get("id", "").strip()
        next_status = form_data.get("next_status", "completed").strip()
        if task_id.isdigit():
            db.execute("UPDATE tasks SET status = ?, completed_at = ? WHERE id = ?", 
                       (next_status, datetime.now().isoformat() if next_status == "completed" else None, int(task_id)))
            self.redirect("/tasks")

    def _handle_task_update(self, form_data: dict, parsed_body: dict) -> None:
        task_id = form_data.get("id", "").strip()
        if not task_id.isdigit(): return
        user_id = int(self.current_user["id"])
        is_admin = "admin" in db.get_user_role_codes(user_id)
        task_row = db.fetch_one("SELECT * FROM tasks WHERE id = ?", (int(task_id),))
        if task_row and _can_manage_task_directly(task_row, user_id, is_admin):
            db.execute("UPDATE tasks SET title = ?, description = ?, priority = ?, due_date = ? WHERE id = ?",
                       (form_data.get("title", "").strip(), form_data.get("description", "").strip(), form_data.get("priority", "medium"), form_data.get("due_date", ""), int(task_id)))
            self.redirect("/tasks?info=task_updated")

    def _handle_task_delete(self, form_data: dict) -> None:
        task_id = form_data.get("id", "").strip()
        if task_id.isdigit():
            db.execute("DELETE FROM tasks WHERE id = ?", (int(task_id),))
            self.redirect("/tasks?info=task_deleted")

    def _handle_task_approve(self, form_data: dict) -> None:
        req_id = form_data.get("request_id", "").strip()
        if req_id.isdigit():
            db.resolve_task_change_request(int(req_id), "approved", int(self.current_user["id"]))
            self.redirect("/tasks?info=request_approved")

    def _handle_task_reject(self, form_data: dict) -> None:
        req_id = form_data.get("request_id", "").strip()
        if req_id.isdigit():
            db.resolve_task_change_request(int(req_id), "rejected", int(self.current_user["id"]))
            self.redirect("/tasks?info=request_rejected")

    def _handle_task_history_delete(self, form_data: dict, parsed_body: dict) -> None:
        ids = _parse_int_list(parsed_body.get("request_ids", []))
        if ids: db.hide_task_change_history_items(int(self.current_user["id"]), ids)
        self.redirect("/tasks")

    def _handle_task_history_clear(self) -> None:
        db.hide_all_task_change_history_for_user(int(self.current_user["id"]))
        self.redirect("/tasks")

    def _handle_attachment_delete(self, form_data: dict) -> None:
        attachment_id = form_data.get("attachment_id", "").strip()
        module_name = form_data.get("module_name", "").strip()
        record_id = form_data.get("record_id", "").strip()
        attachment_name = ""
        if attachment_id.isdigit():
            attachment = db.get_attachment(int(attachment_id))
            if attachment:
                attachment_name = str(attachment["original_name"] or attachment["stored_name"] or "")
                try:
                    file_path = Path(attachment["file_path"])
                    if file_path.exists():
                        file_path.unlink()
                except OSError:
                    pass
                db.delete_attachment(int(attachment_id))
                module_label = {
                    "meetings": "Toplantılar",
                    "documents": "Evraklar",
                    "recurring_documents": "Evraklar",
                }.get(module_name, "Dosyalar")
                self.audit("Dosya Silindi", module_label, int(record_id) if record_id.isdigit() else None, attachment_name)
        if module_name == "meetings" and record_id.isdigit():
            self.redirect(f"/meetings?meeting={record_id}&info=attachment_deleted")
            return
        if module_name in {"documents", "recurring_documents"} and record_id.isdigit():
            source_kind = "recurring" if module_name == "recurring_documents" else "one_time"
            self.redirect(f"/documents?edit_kind={source_kind}&edit_id={record_id}&info=attachment_deleted")
            return
        self.redirect("/") # Fallback redirect

    def _handle_meeting_template_create(self, form_data: dict) -> None:
        title = form_data.get("title", "").strip()
        if title:
            current_max = db.fetch_one("SELECT COALESCE(MAX(sort_order), 0) AS value FROM meeting_templates")
            next_order = int(current_max["value"]) + 1 if current_max else 1
            db.execute(
                "INSERT OR IGNORE INTO meeting_templates (title, sort_order) VALUES (?, ?)",
                (title, next_order),
            )
            self.audit("Başlık Eklendi", "Toplantı Ayarları", details=title)
            self.redirect("/meeting-templates?info=template_saved")
            return
        self.redirect("/meeting-templates?error=template_missing")

    def _handle_meeting_template_delete(self, form_data: dict) -> None:
        template_id = form_data.get("id", "").strip()
        if template_id.isdigit():
            target_template = db.fetch_one("SELECT * FROM meeting_templates WHERE id = ?", (int(template_id),))
            db.execute("DELETE FROM meeting_templates WHERE id = ?", (int(template_id),))
            if target_template:
                self.audit("Başlık Silindi", "Toplantı Ayarları", int(template_id), str(target_template["title"]))
            self.redirect("/meeting-templates?info=template_deleted")
            return
        self.redirect("/meeting-templates?error=template_missing")

    def _handle_meeting_decision_to_task(self, form_data: dict) -> None:
        meeting_id = form_data.get("meeting_id", "").strip()
        decision_text = form_data.get("decision_text", "").strip()
        if decision_text and meeting_id.isdigit():
            existing_task = db.fetch_one(
                "SELECT id FROM tasks WHERE related_type = 'meeting' AND related_id = ? AND title = ?",
                (int(meeting_id), decision_text),
            )
            if not existing_task:
                db.execute(
                    "INSERT INTO tasks (title, responsible_person, description, category, priority, status, due_date, related_type, related_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        decision_text,
                        "",
                        "",
                        "Toplantı",
                        "medium",
                        "pending",
                        "",
                        "meeting",
                        int(meeting_id),
                    ),
                )
                self.audit("Toplantı Kararından Görev Oluşturuldu", "Toplantılar", int(meeting_id), decision_text)
        self.redirect(f"/meetings?meeting={meeting_id}")

    def _handle_meeting_create(self, form_data: dict, parsed_body: dict, uploaded_files: dict) -> None:
        title = form_data.get("title", "").strip()
        if title == "__custom__": title = form_data.get("custom_title", "").strip()
        
        upload = uploaded_files.get("attachment")
        if upload and upload.get("filename") and upload.get("content"):
            v_err = _validate_uploaded_file(upload, db.get_file_settings())
            if v_err:
                self.redirect(f"/meetings?new=1&error={quote(v_err)}")
                return

        meeting_id = db.execute_insert(
            "INSERT INTO meeting_notes (title, meeting_date, agenda, decisions, notes) VALUES (?, ?, ?, ?, ?)",
            (title, form_data.get("meeting_date", ""), _join_form_lines(parsed_body.get("agenda_item", [])), _join_form_lines(parsed_body.get("decision_item", [])), form_data.get("notes", "").strip())
        )
        self.audit("Toplantı Eklendi", "Toplantılar", meeting_id, title)

        if upload and upload.get("filename") and upload.get("content"):
            t_dir = UPLOADS_DIR / "meetings" / str(meeting_id)
            t_dir.mkdir(parents=True, exist_ok=True)
            s_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}_{_sanitize_filename(upload['filename'])}"
            t_path = t_dir / s_name
            t_path.write_bytes(upload["content"])
            db.add_attachment(
                "meetings", int(meeting_id), upload["filename"], s_name, str(t_path), 
                upload.get("content_type", "application/octet-stream"), len(upload["content"]), int(self.current_user["id"])
            )
            self.audit("Toplantı Dosyası Eklendi", "Toplantılar", int(meeting_id), upload["filename"])
            self.redirect(f"/meetings?meeting={meeting_id}&info=meeting_saved_with_attachment")
            return

        self.redirect(f"/meetings?meeting={meeting_id}")

    def _handle_document_attachment(self, form_data: dict, uploaded_files: dict) -> None:
        item_id = form_data.get("document_id", "").strip()
        module_name = form_data.get("kind", "").strip()
        if item_id.isdigit() and module_name in {"documents", "recurring_documents"}:
            source_kind = "recurring" if module_name == "recurring_documents" else "one_time"
            document_row = _fetch_document_row(int(item_id), source_kind)
            current_user_id = int(self.current_user["id"])
            is_admin = "admin" in db.get_user_role_codes(current_user_id)
            upload = uploaded_files.get("attachment")
            if not document_row or not _can_manage_document_directly(document_row, current_user_id, is_admin):
                self.redirect("/documents?error=document_missing")
                return
            if upload and upload.get("filename") and upload.get("content"):
                validation_error = _validate_uploaded_file(upload, db.get_file_settings())
                if validation_error:
                    self.redirect(f"/documents?edit_kind={source_kind}&edit_id={item_id}&error={quote(validation_error)}")
                    return
                target_dir = UPLOADS_DIR / module_name / item_id
                target_dir.mkdir(parents=True, exist_ok=True)
                safe_name = _sanitize_filename(upload["filename"])
                stored_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}_{safe_name}"
                target_path = target_dir / stored_name
                target_path.write_bytes(upload["content"])
                mime_type = upload.get("content_type") or mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
                db.add_attachment(
                    module_name,
                    int(item_id),
                    upload["filename"],
                    stored_name,
                    str(target_path),
                    mime_type,
                    len(upload["content"]),
                    current_user_id,
                )
                self.audit("Evrak Dosyası Eklendi", "Evraklar", int(item_id), upload["filename"])
                self.redirect(f"/documents?edit_kind={source_kind}&edit_id={item_id}&info=attachment_uploaded")
                return
            self.redirect(f"/documents?edit_kind={source_kind}&edit_id={item_id}&error=attachment_missing")
            return
        self.redirect("/documents") # Fallback

    def _handle_document_approve(self, form_data: dict) -> None:
        request_id = form_data.get("request_id", "").strip()
        if request_id.isdigit():
            current_user_id = int(self.current_user["id"])
            request_row = db.get_document_change_request(int(request_id))
            is_admin = "admin" in db.get_user_role_codes(current_user_id)
            if request_row and request_row["status"] == "pending" and (is_admin or int(request_row["owner_user_id"]) == current_user_id):
                try:
                    payload = json.loads(request_row["payload"] or "{}")
                except json.JSONDecodeError:
                    payload = {}
                if request_row["request_type"] == "update":
                    existing_share_ids = db.get_record_user_share_ids(
                        "recurring_documents" if request_row["document_kind"] == "recurring" else "documents",
                        int(request_row["document_id"]),
                    )
                    row = _fetch_document_row(int(request_row["document_id"]), request_row["document_kind"])
                    visibility_type = row["visibility_type"] if row and row["visibility_type"] else ("shared" if existing_share_ids else "private")
                    _apply_document_update(
                        int(request_row["document_id"]),
                        payload.get("source_kind", request_row["document_kind"]),
                        payload.get("target_kind", request_row["document_kind"]),
                        payload.get("title", row["title"] if row else ""),
                        payload.get("frequency", row["frequency"] if row and request_row["document_kind"] == "recurring" else "monthly"),
                        payload.get("next_due_date", row["next_due_date"] if row and request_row["document_kind"] == "recurring" else row["due_date"] if row else ""),
                        payload.get("description", row["notes"] if row and request_row["document_kind"] == "recurring" else row["description"] if row else ""),
                        current_user_id,
                        int(request_row["owner_user_id"]),
                        existing_share_ids,
                        db.get_record_role_share_ids("recurring_documents" if request_row["document_kind"] == "recurring" else "documents", int(request_row["document_id"])),
                        visibility_type,
                    )
                elif request_row["request_type"] == "delete":
                    _delete_document_record(int(request_row["document_id"]), request_row["document_kind"])
                db.resolve_document_change_request(int(request_id), "approved", current_user_id)
                self.audit(
                    "Evrak Talebi Onaylandı",
                    "Evraklar",
                    int(request_row["document_id"]),
                    f"{request_row['request_type']} • {request_row['document_title']}",
                )
                self.redirect("/documents?info=document_request_approved")
                return
        self.redirect("/documents") # Fallback

    def _handle_document_reject(self, form_data: dict) -> None:
        request_id = form_data.get("request_id", "").strip()
        if request_id.isdigit():
            current_user_id = int(self.current_user["id"])
            request_row = db.get_document_change_request(int(request_id))
            is_admin = "admin" in db.get_user_role_codes(current_user_id)
            if request_row and request_row["status"] == "pending" and (is_admin or int(request_row["owner_user_id"]) == current_user_id):
                db.resolve_document_change_request(int(request_id), "rejected", current_user_id)
                self.audit(
                    "Evrak Talebi Reddedildi",
                    "Evraklar",
                    int(request_row["document_id"]),
                    f"{request_row['request_type']} • {request_row['document_title']}",
                )
                self.redirect("/documents?info=document_request_rejected")
                return
        self.redirect("/documents") # Fallback

    def _handle_document_history_delete(self, form_data: dict, parsed_body: dict) -> None:
        current_user_id = int(self.current_user["id"])
        request_id = form_data.get("request_id", "").strip()
        selected_ids = [value.strip() for value in parsed_body.get("request_ids", []) if value.strip().isdigit()]
        request_ids: list[int] = []
        if request_id.isdigit():
            request_ids.append(int(request_id))
        request_ids.extend(int(value) for value in selected_ids if int(value) not in request_ids)
        if request_ids:
            db.hide_document_change_history_items(current_user_id, request_ids)
            self.redirect("/documents?info=document_request_history_deleted")
            return
        self.redirect("/documents?error=document_request_history_empty")

    def _handle_document_history_clear(self) -> None:
        current_user_id = int(self.current_user["id"])
        db.hide_all_document_change_history_for_user(current_user_id)
        self.redirect("/documents?info=document_request_history_cleared")

    def _handle_document_toggle(self, form_data: dict) -> None:
        item_id = form_data.get("id", "").strip()
        kind = form_data.get("kind", "").strip()
        next_state = form_data.get("next_state", "done").strip()
        if item_id.isdigit() and kind == "one_time":
            row = db.fetch_one("SELECT id, title FROM documents WHERE id = ?", (int(item_id),))
            if next_state == "done":
                db.execute(
                    "UPDATE documents SET status = 'submitted', submitted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (int(item_id),),
                )
            else:
                db.execute(
                    "UPDATE documents SET status = 'waiting', submitted_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (int(item_id),),
                )
            if row:
                action = "Evrak Tamamlandı" if next_state == "done" else "Evrak Yeniden Açıldı"
                self.audit(action, "Evraklar", int(item_id), str(row["title"]))
        elif item_id.isdigit() and kind == "recurring":
            row = db.fetch_one("SELECT * FROM recurring_documents WHERE id = ?", (int(item_id),))
            if row:
                if next_state == "done":
                    next_due_date = _advance_due_date(row["next_due_date"], row["frequency"], row["custom_interval_days"])
                    db.execute(
                        "UPDATE recurring_documents SET last_completed_at = CURRENT_TIMESTAMP, next_due_date = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (next_due_date, int(item_id)),
                    )
                else:
                    db.execute(
                        "UPDATE recurring_documents SET last_completed_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (int(item_id),),
                    )
                action = "Tekrarlı Evrak Tamamlandı" if next_state == "done" else "Tekrarlı Evrak Yeniden Açıldı"
                self.audit(action, "Evraklar", int(item_id), str(row["title"]))
        self.redirect("/documents")

    def _handle_supplier_create(self, form_data: dict) -> None:
        phone = _normalize_phone(form_data.get("phone", "").strip())
        company_name = form_data.get("company_name", "").strip()
        db.execute(
            "INSERT INTO suppliers (company_name, contact_name, phone, email, service_type, price_notes, notes, next_contact_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                company_name,
                form_data.get("contact_name", "").strip(),
                phone,
                "",
                form_data.get("service_type", "").strip(),
                "",
                "",
                "",
            ),
        )
        _cleanup_supplier_phone()
        supplier_row = db.fetch_one("SELECT id FROM suppliers ORDER BY id DESC LIMIT 1")
        self.audit("Tedarikçi Eklendi", "Tedarikçiler", int(supplier_row["id"]) if supplier_row else None, company_name)
        self.redirect("/suppliers")

    def _handle_supplier_update(self, form_data: dict) -> None:
        item_id = form_data.get("id", "").strip()
        if item_id.isdigit():
            phone = _normalize_phone(form_data.get("phone", "").strip())
            current_row = db.fetch_one("SELECT id, company_name FROM suppliers WHERE id = ?", (int(item_id),))
            db.execute(
                "UPDATE suppliers SET company_name = ?, contact_name = ?, phone = ?, service_type = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (
                    form_data.get("company_name", "").strip(),
                    form_data.get("contact_name", "").strip(),
                    phone,
                    form_data.get("service_type", "").strip(),
                    int(item_id),
                ),
            )
            _cleanup_supplier_phone()
            if current_row:
                self.audit("Tedarikçi Güncellendi", "Tedarikçiler", int(item_id), f"{current_row['company_name']} -> {form_data.get('company_name', '').strip()}")
        self.redirect(f"/suppliers?supplier={item_id}")

    def _handle_supplier_delete(self, form_data: dict) -> None:
        item_id = form_data.get("id", "").strip()
        if item_id.isdigit():
            current_row = db.fetch_one("SELECT id, company_name FROM suppliers WHERE id = ?", (int(item_id),))
            db.execute("DELETE FROM supplier_interactions WHERE supplier_id = ?", (int(item_id),))
            db.execute("DELETE FROM suppliers WHERE id = ?", (int(item_id),))
            if current_row:
                self.audit("Tedarikçi Silindi", "Tedarikçiler", int(item_id), str(current_row["company_name"]))
        self.redirect("/suppliers")

    def _handle_supplier_note_create(self, form_data: dict) -> None:
        supplier_id = form_data.get("supplier_id", "").strip()
        if supplier_id.isdigit():
            supplier_row = db.fetch_one("SELECT id, company_name FROM suppliers WHERE id = ?", (int(supplier_id),))
            db.execute(
                "INSERT INTO supplier_interactions (supplier_id, interaction_date, notes) VALUES (?, ?, ?)",
                (
                    int(supplier_id),
                    form_data.get("interaction_date", "").strip(),
                    form_data.get("notes", "").strip(),
                ),
            )
            if supplier_row:
                self.audit("Tedarikçi Notu Eklendi", "Tedarikçiler", int(supplier_id), str(supplier_row["company_name"]))
        self.redirect(f"/suppliers?supplier={supplier_id}")

    def _handle_supplier_note_update(self, form_data: dict) -> None:
        supplier_id = form_data.get("supplier_id", "").strip()
        note_id = form_data.get("note_id", "").strip()
        if supplier_id.isdigit() and note_id.isdigit():
            supplier_row = db.fetch_one("SELECT id, company_name FROM suppliers WHERE id = ?", (int(supplier_id),))
            db.execute(
                "UPDATE supplier_interactions SET interaction_date = ?, notes = ? WHERE id = ? AND supplier_id = ?",
                (
                    form_data.get("interaction_date", "").strip(),
                    form_data.get("notes", "").strip(),
                    int(note_id),
                    int(supplier_id),
                ),
            )
            if supplier_row:
                self.audit("Tedarikçi Notu Güncellendi", "Tedarikçiler", int(supplier_id), str(supplier_row["company_name"]))
        self.redirect(f"/suppliers?supplier={supplier_id}")

    def _handle_supplier_note_delete(self, form_data: dict) -> None:
        supplier_id = form_data.get("supplier_id", "").strip()
        note_id = form_data.get("note_id", "").strip()
        if supplier_id.isdigit() and note_id.isdigit():
            supplier_row = db.fetch_one("SELECT id, company_name FROM suppliers WHERE id = ?", (int(supplier_id),))
            db.execute(
                "DELETE FROM supplier_interactions WHERE id = ? AND supplier_id = ?",
                (int(note_id), int(supplier_id)),
            )
            if supplier_row:
                self.audit("Tedarikçi Notu Silindi", "Tedarikçiler", int(supplier_id), str(supplier_row["company_name"]))
        self.redirect(f"/suppliers?supplier={supplier_id}")

    def _handle_event_create(self, form_data: dict, parsed_body: dict) -> None:
        event_levels = _normalize_event_levels(parsed_body.get("level", []))
        start_date = form_data.get("event_date", "").strip()
        end_date = form_data.get("end_date", "").strip() or start_date
        title = form_data.get("title", "").strip()
        time_range = form_data.get("time_range", "").strip()
        notes = form_data.get("notes", "").strip()
        db.execute(
            "INSERT INTO events (title, event_date, end_date, level, time_range, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (
                title,
                start_date,
                end_date,
                ",".join(event_levels),
                time_range,
                notes,
            ),
        )
        event_row = db.fetch_one("SELECT id FROM events ORDER BY id DESC LIMIT 1")
        self.audit("Etkinlik Eklendi", "Etkinlikler", int(event_row["id"]) if event_row else None, f"{title} • {_format_date_range(start_date, end_date)}")
        self.redirect("/events")

    def _handle_event_update(self, form_data: dict, parsed_body: dict) -> None:
        item_id = form_data.get("id", "").strip()
        if item_id.isdigit():
            event_levels = _normalize_event_levels(parsed_body.get("level", []))
            start_date = form_data.get("event_date", "").strip()
            end_date = form_data.get("end_date", "").strip() or start_date
            time_range = form_data.get("time_range", "").strip()
            notes = form_data.get("notes", "").strip()
            current_row = db.fetch_one("SELECT id, title FROM events WHERE id = ?", (int(item_id),))
            db.execute(
                "UPDATE events SET title = ?, event_date = ?, end_date = ?, level = ?, time_range = ?, notes = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (
                    form_data.get("title", "").strip(),
                    start_date,
                    end_date,
                    ",".join(event_levels),
                    time_range,
                    notes,
                    int(item_id),
                ),
            )
            if current_row:
                self.audit("Etkinlik Güncellendi", "Etkinlikler", int(item_id), f"{current_row['title']} -> {form_data.get('title', '').strip()}")
        self.redirect(f"/events?edit={item_id}")

    def _handle_event_delete(self, form_data: dict) -> None:
        item_id = form_data.get("id", "").strip()
        if item_id.isdigit():
            current_row = db.fetch_one("SELECT id, title FROM events WHERE id = ?", (int(item_id),))
            db.execute("DELETE FROM events WHERE id = ?", (int(item_id),))
            if current_row:
                self.audit("Etkinlik Silindi", "Etkinlikler", int(item_id), str(current_row["title"]))
        self.redirect("/events")

    def _handle_user_create(self, form_data: dict, parsed_body: dict) -> None:
        full_name = form_data.get("full_name", "").strip()
        username = form_data.get("username", "").strip()
        email = form_data.get("email", "").strip()
        phone = form_data.get("phone", "").strip()
        password = form_data.get("password", "")
        selected_company_ids = _parse_int_list(parsed_body.get("company_ids", []))
        selected_branch_ids = _parse_int_list(parsed_body.get("branch_ids", []))
        role_code = form_data.get("role_code", "ogretmen").strip()
        is_active = form_data.get("is_active", "1").strip() == "1"
        normalized_company_ids, normalized_branch_ids, relation_error = _normalize_user_company_branch_selection(selected_company_ids, selected_branch_ids)
        defaults = {
            "full_name": full_name,
            "username": username,
            "email": email,
            "phone": phone,
            "company_ids": [str(value) for value in normalized_company_ids or selected_company_ids],
            "branch_ids": [str(value) for value in normalized_branch_ids or selected_branch_ids],
            "role_code": role_code or "ogretmen",
            "is_active": "1" if is_active else "0",
        }
        if relation_error:
            self.render_users_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": relation_error},
                form_defaults=defaults,
            )
            return
        company_id = normalized_company_ids[0] if normalized_company_ids else None
        branch_id = normalized_branch_ids[0] if normalized_branch_ids else None
        if not full_name or not username or not password:
            self.render_users_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Ad soyad, kullanıcı adı ve şifre zorunludur."},
                form_defaults=defaults,
            )
            return
        if len(password) < 6:
            self.render_users_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Şifre en az 6 karakter olmalı."},
                form_defaults=defaults,
            )
            return
        if db.get_user_by_username(username):
            self.render_users_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Bu kullanıcı adı zaten kullanılıyor."},
                form_defaults=defaults,
            )
            return
        if email and db.get_user_by_email(email):
            self.render_users_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Bu e-posta başka bir kullanıcıda kayıtlı."},
                form_defaults=defaults,
            )
            return
        try:
            user_id = db.create_user(
                username=username,
                password=password,
                full_name=full_name,
                email=email,
                phone=phone,
                company_id=company_id,
                company_ids=normalized_company_ids,
                branch_id=branch_id,
                branch_ids=normalized_branch_ids,
                role_codes=[role_code],
            )
            if not is_active:
                db.update_user(
                    user_id=user_id,
                    username=username,
                    full_name=full_name,
                    email=email,
                    phone=phone,
                    company_id=company_id,
                    company_ids=normalized_company_ids,
                    branch_id=branch_id,
                    branch_ids=normalized_branch_ids,
                    is_active=False,
                    role_codes=[role_code],
                )
        except Exception:
            self.render_users_state(
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
                feedback={"error": "Kullanıcı eklenirken bir hata oluştu. Bilgileri kontrol edip tekrar deneyin."},
                form_defaults=defaults,
            )
            return
        role_name = next((row["name"] for row in db.list_roles() if row["code"] == role_code), role_code)
        self.audit("Kullanıcı Eklendi", "Kullanıcılar", user_id, f"{full_name} • Rol: {role_name}")
        self.render_users_state(feedback={"info": "Kullanıcı başarıyla eklendi."})

    def _handle_user_update(self, form_data: dict, parsed_body: dict) -> None:
        user_id = form_data.get("id", "").strip()
        full_name = form_data.get("full_name", "").strip()
        username = form_data.get("username", "").strip()
        email = form_data.get("email", "").strip()
        phone = form_data.get("phone", "").strip()
        password = form_data.get("password", "")
        selected_company_ids = _parse_int_list(parsed_body.get("company_ids", []))
        selected_branch_ids = _parse_int_list(parsed_body.get("branch_ids", []))
        role_code = form_data.get("role_code", "ogretmen").strip()
        is_active = form_data.get("is_active", "1").strip() == "1"
        normalized_company_ids, normalized_branch_ids, relation_error = _normalize_user_company_branch_selection(selected_company_ids, selected_branch_ids)
        company_id = normalized_company_ids[0] if normalized_company_ids else None
        branch_id = normalized_branch_ids[0] if normalized_branch_ids else None
        if relation_error:
            self.render_users_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": relation_error},
                edit_item=db.get_user_by_id(int(user_id)) if user_id.isdigit() else None,
            )
            return
        if not user_id.isdigit() or not full_name or not username:
            target = db.get_user_by_id(int(user_id))
            if target:
                role_codes = ",".join(db.get_user_role_codes(int(user_id)))
                target = dict(target)
                target["role_codes"] = role_codes
            self.render_users_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Güncelleme için gerekli alanları doldurun."},
                edit_item=target,
            )
            return
        if password and len(password) < 6:
            target = db.get_user_by_id(int(user_id))
            if target:
                role_codes = ",".join(db.get_user_role_codes(int(user_id)))
                target = dict(target)
                target["role_codes"] = role_codes
            self.render_users_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Şifre en az 6 karakter olmalı."},
                edit_item=target,
            )
            return
        existing_username = db.get_user_by_username(username)
        existing_email = db.get_user_by_email(email) if email else None
        if existing_username and existing_username["id"] != int(user_id):
            target = db.get_user_by_id(int(user_id))
            if target:
                role_codes = ",".join(db.get_user_role_codes(int(user_id)))
                target = dict(target)
                target["role_codes"] = role_codes
            self.render_users_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Bu kullanıcı adı zaten kullanılıyor."},
                edit_item=target,
            )
            return
        if existing_email and existing_email["id"] != int(user_id):
            target = db.get_user_by_id(int(user_id))
            if target:
                role_codes = ",".join(db.get_user_role_codes(int(user_id)))
                target = dict(target)
                target["role_codes"] = role_codes
            self.render_users_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Bu e-posta başka bir kullanıcıda kayıtlı."},
                edit_item=target,
            )
            return
        try:
            before_user = db.get_user_by_id(int(user_id))
            db.update_user(
                user_id=int(user_id),
                username=username,
                full_name=full_name,
                email=email,
                phone=phone,
                company_id=company_id,
                company_ids=normalized_company_ids,
                branch_id=branch_id,
                branch_ids=normalized_branch_ids,
                is_active=is_active,
                role_codes=[role_code],
                password=password,
            )
        except Exception:
            target = db.get_user_by_id(int(user_id))
            if target:
                role_codes = ",".join(db.get_user_role_codes(int(user_id)))
                target = dict(target)
                target["role_codes"] = role_codes
            self.render_users_state(
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
                feedback={"error": "Kullanıcı güncellenirken bir hata oluştu."},
                edit_item=target,
            )
            return
        previous_name = before_user["full_name"] if before_user and before_user["full_name"] else (before_user["username"] if before_user else username)
        self.audit("Kullanıcı Güncellendi", "Kullanıcılar", int(user_id), f"{previous_name} -> {full_name}")
        self.render_users_state(feedback={"info": "Kullanıcı bilgileri güncellendi."})

    def _handle_user_toggle(self, form_data: dict) -> None:
        user_id = form_data.get("id", "").strip()
        if user_id.isdigit():
            target_user = db.get_user_by_id(int(user_id))
            if target_user:
                role_codes = db.get_user_role_codes(int(user_id))
                if "admin" not in role_codes:
                    db.update_user(
                        user_id=int(user_id),
                        username=target_user["username"],
                        full_name=target_user["full_name"] or "",
                        email=target_user["email"] or "",
                        phone=target_user["phone"] or "",
                        company_id=row_value(target_user, "company_id"),
                        company_ids=db.get_user_company_ids(int(user_id)),
                        branch_id=row_value(target_user, "branch_id"),
                        branch_ids=db.get_user_branch_ids(int(user_id)),
                        is_active=not bool(target_user["is_active"]),
                        role_codes=role_codes,
                        password="",
                    )
                    yeni_durum = "Aktif" if not bool(target_user["is_active"]) else "Pasif"
                    self.audit("Kullanıcı Durumu Değişti", "Kullanıcılar", int(user_id), f"{target_user['full_name'] or target_user['username']} -> {yeni_durum}")
                    self.render_users_state(feedback={"info": "Kullanıcı durumu güncellendi."})
                    return
        self.render_users_state(
            status=HTTPStatus.BAD_REQUEST,
            feedback={"error": "Bu kullanıcı için durum değişikliği yapılamadı."},
        )

    def _handle_company_create(self, form_data: dict) -> None:
        name = form_data.get("name", "").strip()
        code = form_data.get("code", "").strip()
        defaults = {"name": name, "code": code}
        if not name or not code:
            self.render_companies_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Firma adı ve kısa kod zorunludur."},
                form_defaults=defaults,
            )
            return
        try:
            db.create_company(name, code)
        except Exception:
            self.render_companies_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Firma eklenemedi. Ad veya kod zaten kullanılıyor olabilir."},
                form_defaults=defaults,
            )
            return
        self.audit("Firma Eklendi", "Firmalar", details=f"{name} ({code})")
        self.render_companies_state(feedback={"info": "Firma eklendi."})

    def _handle_company_update(self, form_data: dict) -> None:
        item_id = form_data.get("id", "").strip()
        name = form_data.get("name", "").strip()
        code = form_data.get("code", "").strip()
        target = db.get_company_by_id(int(item_id)) if item_id.isdigit() else None
        if not target or not name or not code:
            self.render_companies_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Firma güncelleme bilgileri eksik."},
                edit_item=target,
            )
            return
        try:
            db.update_company(int(item_id), name, code)
        except Exception:
            self.render_companies_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Firma güncellenemedi. Ad veya kod kullanımda olabilir."},
                edit_item=target,
            )
            return
        self.audit("Firma Güncellendi", "Firmalar", int(item_id), f"{target['name']} -> {name}")
        self.render_companies_state(feedback={"info": "Firma güncellendi."})

    def _handle_company_delete(self, form_data: dict) -> None:
        item_id = form_data.get("id", "").strip()
        target = db.get_company_by_id(int(item_id)) if item_id.isdigit() else None
        if not target:
            self.render_companies_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Silinecek firma bulunamadı."},
            )
            return
        if db.count_users_for_company(int(item_id)) > 0 or db.list_branches(int(item_id)):
            self.render_companies_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Firmaya bağlı kullanıcı veya şubeler var. Önce onları taşıyın ya da silin."},
            )
            return
        db.delete_company(int(item_id))
        self.audit("Firma Silindi", "Firmalar", int(item_id), str(target["name"]))
        self.render_companies_state(feedback={"info": "Firma silindi."})

    def _handle_branch_create(self, form_data: dict) -> None:
        company_id_raw = form_data.get("company_id", "").strip()
        name = form_data.get("name", "").strip()
        code = form_data.get("code", "").strip()
        defaults = {"company_id": company_id_raw, "name": name, "code": code}
        company_id = int(company_id_raw) if company_id_raw.isdigit() else None
        if not company_id or not db.get_company_by_id(company_id) or not name or not code:
            self.render_branches_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Şube için firma, ad ve kısa kod zorunludur."},
                form_defaults=defaults,
            )
            return
        try:
            db.create_branch(company_id, name, code)
        except Exception:
            self.render_branches_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Şube eklenemedi. Kod aynı firma içinde kullanımda olabilir."},
                form_defaults=defaults,
            )
            return
        self.audit("Şube Eklendi", "Şubeler", details=f"{name} ({code})")
        self.render_branches_state(feedback={"info": "Şube eklendi."})

    def _handle_branch_update(self, form_data: dict) -> None:
        item_id = form_data.get("id", "").strip()
        company_id_raw = form_data.get("company_id", "").strip()
        name = form_data.get("name", "").strip()
        code = form_data.get("code", "").strip()
        target = db.get_branch_by_id(int(item_id)) if item_id.isdigit() else None
        company_id = int(company_id_raw) if company_id_raw.isdigit() else None
        if not target or not company_id or not db.get_company_by_id(company_id) or not name or not code:
            self.render_branches_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Şube güncelleme bilgileri eksik."},
                edit_item=target,
            )
            return
        try:
            db.update_branch(int(item_id), company_id, name, code)
        except Exception:
            self.render_branches_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Şube güncellenemedi. Kod aynı firma içinde kullanımda olabilir."},
                edit_item=target,
            )
            return
        self.audit("Şube Güncellendi", "Şubeler", int(item_id), f"{target['name']} -> {name}")
        self.render_branches_state(feedback={"info": "Şube güncellendi."})

    def _handle_branch_delete(self, form_data: dict) -> None:
        item_id = form_data.get("id", "").strip()
        target = db.get_branch_by_id(int(item_id)) if item_id.isdigit() else None
        if not target:
            self.render_branches_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Silinecek şube bulunamadı."},
            )
            return
        if db.count_users_for_branch(int(item_id)) > 0:
            self.render_branches_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Bu şubeye bağlı kullanıcılar var. Önce kullanıcı atamalarını değiştirin."},
            )
            return
        db.delete_branch(int(item_id))
        self.audit("Şube Silindi", "Şubeler", int(item_id), str(target["name"]))
        self.render_branches_state(feedback={"info": "Şube silindi."})

    def _handle_role_create(self, form_data: dict) -> None:
        name = form_data.get("name", "").strip()
        description = form_data.get("description", "").strip()
        defaults = {"name": name, "description": description}
        if not name:
            self.render_roles_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Rol adı zorunludur."},
                form_defaults=defaults,
            )
            return
        role_code = _slugify_role_code(name)
        if not role_code:
            self.render_roles_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Geçerli bir rol adı girin."},
                form_defaults=defaults,
            )
            return
        if db.get_role_by_code(role_code):
            self.render_roles_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Bu role ait kod zaten var. Farklı bir ad deneyin."},
                form_defaults=defaults,
            )
            return
        try:
            db.create_role(role_code, name, description)
        except Exception:
            self.render_roles_state(
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
                feedback={"error": "Rol eklenirken bir hata oluştu."},
                form_defaults=defaults,
            )
            return
        self.audit("Rol Eklendi", "Roller", details=f"{name} ({role_code})")
        self.render_roles_state(feedback={"info": "Rol eklendi."})

    def _handle_role_update(self, form_data: dict) -> None:
        code = form_data.get("code", "").strip()
        name = form_data.get("name", "").strip()
        description = form_data.get("description", "").strip()
        target = db.get_role_by_code(code) if code else None
        if not target or code in db.SYSTEM_ROLE_CODES:
            self.render_roles_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Bu rol düzenlenemez."},
            )
            return
        if not name:
            self.render_roles_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Rol adı zorunludur."},
                edit_item=dict(target),
            )
            return
        try:
            db.update_role(code, name, description)
        except Exception:
            self.render_roles_state(
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
                feedback={"error": "Rol güncellenirken bir hata oluştu."},
                edit_item=dict(target),
            )
            return
        self.audit("Rol Güncellendi", "Roller", int(target["id"]), f"{target['name']} -> {name}")
        self.render_roles_state(feedback={"info": "Rol güncellendi."})

    def _handle_role_delete(self, form_data: dict) -> None:
        code = form_data.get("code", "").strip()
        target = db.get_role_by_code(code) if code else None
        if not target:
            self.render_roles_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Silinecek rol bulunamadı."},
            )
            return
        if code in db.SYSTEM_ROLE_CODES:
            self.render_roles_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Sistem rolleri silinemez."},
            )
            return
        if db.count_users_for_role(code) > 0:
            self.render_roles_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Bu role bağlı kullanıcılar var. Önce kullanıcı rollerini değiştirin."},
            )
            return
        try:
            db.delete_role(code)
        except Exception:
            self.render_roles_state(
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
                feedback={"error": "Rol silinirken bir hata oluştu."},
            )
            return
        self.audit("Rol Silindi", "Roller", int(target["id"]), f"{target['name']} ({code})")
        self.render_roles_state(feedback={"info": "Rol silindi."})

    def _handle_permission_update(self, form_data: dict, parsed_body: dict) -> None:
        role_code = form_data.get("role_code", "").strip()
        if not role_code:
            self.render_permissions_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Önce bir rol seçin."},
            )
            return
        permission_codes = parsed_body.get("permission_code", [])
        db.set_role_permissions(role_code, permission_codes)
        role_row = db.get_role_by_code(role_code)
        self.audit(
            "Yetkiler Güncellendi",
            "Yetkiler",
            int(role_row["id"]) if role_row else None,
            f"{role_row['name'] if role_row else role_code} • {len(permission_codes)} izin",
        )
        self.render_permissions_state(
            role_code=role_code,
            feedback={"info": "Rol yetkileri güncellendi."},
        )

    def _handle_notification_settings_save(self, form_data: dict) -> None:
        current_user_id = int(self.current_user["id"])
        settings = {
            "badge_pending_requests": 1 if form_data.get("badge_pending_requests", "") == "1" else 0,
            "approval_items": 1 if form_data.get("approval_items", "") == "1" else 0,
            "outgoing_items": 1 if form_data.get("outgoing_items", "") == "1" else 0,
            "task_alerts": 1 if form_data.get("task_alerts", "") == "1" else 0,
            "document_alerts": 1 if form_data.get("document_alerts", "") == "1" else 0,
            "event_reminders": 1 if form_data.get("event_reminders", "") == "1" else 0,
        }
        db.save_notification_settings(current_user_id, settings)
        aktif_sayi = sum(int(value) for value in settings.values())
        self.audit("Bildirim Ayarları Kaydedildi", "Bildirim Ayarları", current_user_id, f"{aktif_sayi} ayar açık")
        self.render_notification_settings_state(feedback={"info": "Bildirim ayarları kaydedildi."})

    def _handle_backup_create(self) -> None:
        try:
            backup_path = db.create_backup_now()
        except OSError:
            self.render_backup_settings_state(feedback={"error": "Yedek oluşturulamadı. Dosya izinlerini kontrol edin."})
            return
        self.audit("Manuel Yedek Alındı", "Yedekleme", details=backup_path.name)
        self.redirect("/backup-settings?info=created")

    def _handle_file_settings_save(self, form_data: dict) -> None:
        raw_extensions = form_data.get("allowed_extensions", "")
        max_size_raw = form_data.get("max_file_size_mb", "").strip()
        normalized_extensions = _normalize_extension_list(raw_extensions)
        if not normalized_extensions:
            self.render_file_settings_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "En az bir dosya uzantısı tanımlayın."},
                form_defaults={
                    "allowed_extensions": raw_extensions,
                    "max_file_size_mb": max_size_raw,
                },
            )
            return
        try:
            max_file_size_mb = max(1, min(int(max_size_raw), 100))
        except ValueError:
            self.render_file_settings_state(
                status=HTTPStatus.BAD_REQUEST,
                feedback={"error": "Maksimum boyut için 1 ile 100 arasında bir sayı girin."},
                form_defaults={
                    "allowed_extensions": raw_extensions,
                    "max_file_size_mb": max_size_raw,
                },
            )
            return
        db.save_file_settings(normalized_extensions, max_file_size_mb)
        self.audit("Dosya Ayarları Kaydedildi", "Dosya Ayarları", details=f"{normalized_extensions} • {max_file_size_mb} MB")
        self.render_file_settings_state(feedback={"info": "Dosya ayarları kaydedildi."})
    def _handle_meeting_create(self, form_data: dict, parsed_body: dict, uploaded_files: dict) -> None:
        title = form_data.get("title", "").strip()
        if title == "__custom__": title = form_data.get("custom_title", "").strip()
        meeting_id = db.execute_insert(
            "INSERT INTO meeting_notes (title, meeting_date, agenda, decisions, notes) VALUES (?, ?, ?, ?, ?)",
            (title, form_data.get("meeting_date", ""), _join_form_lines(parsed_body.get("agenda_item", [])), _join_form_lines(parsed_body.get("decision_item", [])), form_data.get("notes", "").strip())
        )
        self.redirect(f"/meetings?meeting={meeting_id}")

    def _handle_meeting_update(self, form_data: dict, parsed_body: dict) -> None:
        mid = form_data.get("id", "").strip()
        if mid.isdigit():
            db.execute("UPDATE meeting_notes SET title = ?, meeting_date = ?, agenda = ?, decisions = ?, notes = ? WHERE id = ?",
                       (form_data.get("title", "").strip(), form_data.get("meeting_date", ""), _join_form_lines(parsed_body.get("agenda_item", [])), _join_form_lines(parsed_body.get("decision_item", [])), form_data.get("notes", "").strip(), int(mid)))
            self.redirect(f"/meetings?meeting={mid}")

    def _handle_meeting_delete(self, form_data: dict) -> None:
        mid = form_data.get("id", "").strip()
        if mid.isdigit():
            db.execute("DELETE FROM meeting_notes WHERE id = ?", (int(mid),))
            self.redirect("/meetings")

    def _handle_meeting_attachment(self, form_data: dict, uploaded_files: dict) -> None:
        mid = form_data.get("meeting_id", "").strip()
        if mid.isdigit(): self.redirect(f"/meetings?meeting={mid}")

    def _handle_document_create(self, form_data: dict, parsed_body: dict, uploaded_files: dict) -> None:
        kind = form_data.get("kind", "one_time").strip()
        frequency = form_data.get("frequency", "monthly").strip()
        description = form_data.get("description", "").strip()
        user_id = int(self.current_user["id"])
        share_user_ids = _normalize_share_user_ids(parsed_body.get("share_user_ids", []), user_id)
        share_role_ids = _normalize_share_role_ids(parsed_body.get("share_role_ids", []))
        visibility_type = "shared" if share_user_ids or share_role_ids else "private"
        
        upload = uploaded_files.get("attachment")
        if upload and upload.get("filename") and upload.get("content"):
            v_err = _validate_uploaded_file(upload, db.get_file_settings())
            if v_err:
                self.redirect(f"/documents?error={quote(v_err)}")
                return

        title = form_data.get("title", "").strip()
        due_date = form_data.get("next_due_date", "").strip()
        
        if kind == "one_time":
            doc_id = db.execute_insert(
                "INSERT INTO documents (title, institution, document_type, description, status, due_date, responsible_person, owner_user_id, visibility_type, created_by, updated_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (title, "", "Genel Evrak", description, "waiting", due_date, form_data.get("responsible_person", "").strip(), user_id, visibility_type, user_id, user_id),
            )
            db.replace_record_user_shares("documents", doc_id, share_user_ids)
            db.replace_record_role_shares("documents", doc_id, share_role_ids)
            module = "documents"
        else:
            doc_id = db.execute_insert(
                "INSERT INTO recurring_documents (title, category, frequency, next_due_date, responsible_person, notes, owner_user_id, visibility_type, created_by, updated_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (title, "Genel", frequency, due_date, form_data.get("responsible_person", "").strip(), description, user_id, visibility_type, user_id, user_id),
            )
            db.replace_record_user_shares("recurring_documents", doc_id, share_user_ids)
            db.replace_record_role_shares("recurring_documents", doc_id, share_role_ids)
            module = "recurring_documents"

        self.audit("Evrak Eklendi", "Evraklar", doc_id, f"{title} • {'Tekrarlı' if kind == 'recurring' else 'Tek Seferlik'}")
        
        if upload and upload.get("filename") and upload.get("content"):
            t_dir = UPLOADS_DIR / module / str(doc_id)
            t_dir.mkdir(parents=True, exist_ok=True)
            s_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}_{_sanitize_filename(upload['filename'])}"
            t_path = t_dir / s_name
            t_path.write_bytes(upload["content"])
            db.add_attachment(module, int(doc_id), upload["filename"], s_name, str(t_path), upload.get("content_type", "application/octet-stream"), len(upload["content"]), user_id)
            self.audit("Evrak Dosyası Eklendi", "Evraklar", int(doc_id), upload["filename"])
            self.redirect("/documents?info=document_created_with_attachment")
            return
            
        self.redirect("/documents?info=document_created")

    def _handle_document_update(self, form_data: dict, parsed_body: dict) -> None:
        item_id = form_data.get("id", "").strip()
        target_kind = form_data.get("kind", "one_time").strip()
        frequency = form_data.get("frequency", "monthly").strip()
        source_kind = form_data.get("source_kind", target_kind).strip()
        u_id = int(self.current_user["id"])
        if item_id.isdigit():
            is_admin = "admin" in db.get_user_role_codes(u_id)
            row = _fetch_document_row(int(item_id), source_kind)
            if not row:
                self.redirect("/documents?error=document_missing")
                return
            s_u_ids = _normalize_share_user_ids(parsed_body.get("share_user_ids", []), u_id)
            s_r_ids = _normalize_share_role_ids(parsed_body.get("share_role_ids", []))
            vis = "shared" if s_u_ids or s_r_ids else "private"
            if _can_manage_document_directly(row, u_id, is_admin):
                _apply_document_update(int(item_id), source_kind, target_kind, form_data.get("title", "").strip(), frequency, form_data.get("next_due_date", "").strip(), form_data.get("description", "").strip(), u_id, int(row["owner_user_id"]) if row["owner_user_id"] else u_id, s_u_ids, s_r_ids, vis)
                self.audit("Evrak Güncellendi", "Evraklar", int(item_id), f"{row['title']} -> {form_data.get('title', '').strip()}")
                self.redirect("/documents?info=document_updated")
                return
            if not _can_request_document_change(row, source_kind, u_id):
                self.redirect("/documents?error=document_missing")
                return
            owner = int(row["owner_user_id"]) if row["owner_user_id"] else 0
            db.save_document_change_request(int(item_id), source_kind, owner, u_id, "update", {"source_kind": source_kind, "target_kind": target_kind, "title": form_data.get("title", "").strip(), "frequency": frequency, "next_due_date": form_data.get("next_due_date", "").strip(), "description": form_data.get("description", "").strip()})
            self.audit("Evrak Düzenleme Talebi Gönderildi", "Evraklar", int(item_id), str(row["title"]))
            self.redirect("/documents?info=document_request_sent")

    def _handle_document_delete(self, form_data: dict) -> None:
        item_id = form_data.get("id", "").strip()
        kind = form_data.get("kind", "").strip()
        if item_id.isdigit() and kind in {"one_time", "recurring"}:
            u_id = int(self.current_user["id"])
            is_admin = "admin" in db.get_user_role_codes(u_id)
            row = _fetch_document_row(int(item_id), kind)
            if not row:
                self.redirect("/documents?error=document_missing")
                return
            if _can_manage_document_directly(row, u_id, is_admin):
                _delete_document_record(int(item_id), kind)
                self.audit("Evrak Silindi", "Evraklar", int(item_id), str(row["title"]))
                self.redirect("/documents?info=document_deleted")
                return
            if not _can_request_document_change(row, kind, u_id):
                self.redirect("/documents?error=document_missing")
                return
            owner = int(row["owner_user_id"]) if row["owner_user_id"] else 0
            db.save_document_change_request(int(item_id), kind, owner, u_id, "delete", {"title": row["title"], "source_kind": kind})
            self.audit("Evrak Silme Talebi Gönderildi", "Evraklar", int(item_id), str(row["title"]))
            self.redirect("/documents?info=document_request_sent")

    def _handle_user_create(self, form_data: dict, parsed_body: dict) -> None:
        username = form_data.get("username", "").strip()
        if not db.get_user_by_username(username):
            db.create_user(username, form_data.get("password", "123456"), form_data.get("full_name", ""), role_codes=[form_data.get("role_code", "ogretmen")])
        self.redirect("/users")

    def _handle_user_update(self, form_data: dict, parsed_body: dict) -> None:
        uid = form_data.get("id", "").strip()
        if uid.isdigit():
            db.update_user(int(uid), form_data.get("username"), form_data.get("full_name"), form_data.get("email"), form_data.get("phone"), None, [], None, [], True, [form_data.get("role_code", "ogretmen")])
        self.redirect("/users")

    def _handle_user_toggle(self, form_data: dict) -> None:
        uid = form_data.get("id", "").strip()
        if uid.isdigit():
            user = db.get_user_by_id(int(uid))
            if user: db.execute("UPDATE users SET is_active = ? WHERE id = ?", (0 if user["is_active"] else 1, int(uid)))
        self.redirect("/users")

    def download_attachment(self, query: dict[str, list[str]]) -> None:
        attachment_id = query.get("id", [""])[0]
        if not attachment_id.isdigit():
            self.respond(HTTPStatus.NOT_FOUND, b"Not found", content_type="text/plain; charset=utf-8")
            return
        attachment = db.get_attachment(int(attachment_id))
        if not attachment:
            self.respond(HTTPStatus.NOT_FOUND, b"Not found", content_type="text/plain; charset=utf-8")
            return
        file_path = Path(attachment["file_path"])
        if not file_path.exists() or not file_path.is_file():
            self.respond(HTTPStatus.NOT_FOUND, b"Not found", content_type="text/plain; charset=utf-8")
            return
        original_name = attachment["original_name"] or file_path.name
        headers = [("Content-Disposition", f'attachment; filename="{original_name}"')]
        self.respond(HTTPStatus.OK, file_path.read_bytes(), content_type=attachment["mime_type"] or "application/octet-stream", extra_headers=headers)

    def download_backup(self, query: dict[str, list[str]]) -> None:
        file_name = query.get("name", [""])[0]
        backup_path = db.get_backup_path(file_name)
        if not backup_path:
            self.respond(HTTPStatus.NOT_FOUND, b"Not found", content_type="text/plain; charset=utf-8")
            return
        headers = [("Content-Disposition", f'attachment; filename="{backup_path.name}"')]
        self.respond(
            HTTPStatus.OK,
            backup_path.read_bytes(),
            content_type="application/octet-stream",
            extra_headers=headers,
        )

    def parse_request_body(self) -> tuple[dict[str, list[str]], dict[str, str], dict[str, dict]]:
        content_type = self.headers.get("Content-Type", "")
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_bytes = self.rfile.read(content_length)
        if content_type.startswith("multipart/form-data"):
            parsed_body, files = _parse_multipart_form_data(content_type, raw_bytes)
            form_data = {key: values[0] for key, values in parsed_body.items() if values}
            return parsed_body, form_data, files
        raw_body = raw_bytes.decode("utf-8")
        parsed_body = parse_qs(raw_body)
        form_data = {key: values[0] for key, values in parsed_body.items()}
        return parsed_body, form_data, {}

    def respond(self, status: HTTPStatus, content: bytes, content_type: str = "text/html; charset=utf-8", extra_headers: list[tuple[str, str]] | None = None) -> None:
        self.send_response(status.value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        for key, value in extra_headers or []:
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(content)

    def redirect(self, location: str, extra_headers: list[tuple[str, str]] | None = None) -> None:
        self.send_response(HTTPStatus.SEE_OTHER.value)
        self.send_header("Location", location)
        for key, value in extra_headers or []:
            self.send_header(key, value)
        self.end_headers()

    def get_current_user(self):
        cookie_header = self.headers.get("Cookie", "")
        if not cookie_header:
            return None
        cookies = SimpleCookie()
        cookies.load(cookie_header)
        session_cookie = cookies.get(AUTH_COOKIE_NAME)
        if not session_cookie:
            return None
        return db.get_session_user(session_cookie.value)

    def get_current_permissions(self) -> set[str]:
        if not getattr(self, "current_user", None):
            return set()
        return db.get_user_permissions(self.current_user["id"])

    def audit(self, action: str, module_name: str, record_id: int | None = None, details: str = "") -> None:
        user_id = None
        if getattr(self, "current_user", None):
            try:
                user_id = int(self.current_user["id"])
            except Exception:
                user_id = None
        try:
            db.add_audit_log(user_id, action, module_name, record_id, details)
        except Exception:
            pass

    def get_allowed_paths(self) -> set[str]:
        allowed = {"/", "/search", "/notifications", "/notification-settings"}
        permissions = getattr(self, "current_permissions", set())
        for permission_code, path in MODULE_ALLOWED_PATHS.items():
            if permission_code in permissions:
                allowed.add(path)
        if "roles.manage" in permissions:
            allowed.add("/backup-settings")
            allowed.add("/file-settings")
            allowed.add("/audit-logs")
            allowed.add("/companies")
            allowed.add("/branches")
            allowed.add("/permissions")
            allowed.add("/meeting-templates")
        return allowed

    def get_notification_badge_count(self) -> int:
        if not getattr(self, "current_user", None):
            return 0
        try:
            user_id = int(self.current_user["id"])
            settings = db.get_notification_settings(user_id)
            if not int(settings.get("badge_pending_requests", 1)):
                return 0
            return len(db.list_pending_task_change_requests(user_id)) + len(db.list_pending_document_change_requests(user_id))
        except Exception:
            return 0

    def with_notification_badge(self, user):
        if not user:
            return user
        try:
            data = dict(user)
            data["_notification_badge_count"] = getattr(self, "notification_badge_count", 0)
            return data
        except Exception:
            return user

    def handle_login(self, form_data: dict[str, str]) -> None:
        username = form_data.get("username", "").strip()
        password = form_data.get("password", "")
        next_path = form_data.get("next", "/") or "/"
        user = db.authenticate_user(username, password)
        if not user:
            self.respond(HTTPStatus.UNAUTHORIZED, login_page("Kullanıcı adı veya şifre hatalı.", next_path))
            return
        session_token = db.create_session(user["id"])
        cookie = f"{AUTH_COOKIE_NAME}={session_token}; Path=/; HttpOnly; SameSite=Lax"
        self.redirect(next_path, [("Set-Cookie", cookie)])

    def handle_logout(self) -> None:
        cookie_header = self.headers.get("Cookie", "")
        cookies = SimpleCookie()
        cookies.load(cookie_header)
        session_cookie = cookies.get(AUTH_COOKIE_NAME)
        if session_cookie:
            db.delete_session(session_cookie.value)
        self.redirect("/login", [("Set-Cookie", f"{AUTH_COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax")])

    def handle_setup(self, form_data: dict[str, str]) -> None:
        full_name = form_data.get("full_name", "").strip()
        username = form_data.get("username", "").strip()
        email = form_data.get("email", "").strip()
        password = form_data.get("password", "")
        password_confirm = form_data.get("password_confirm", "")
        defaults = {"full_name": full_name, "username": username, "email": email}
        if not full_name or not username or not password:
            self.respond(HTTPStatus.BAD_REQUEST, setup_page("Zorunlu alanları doldurun.", defaults))
            return
        if len(password) < 6:
            self.respond(HTTPStatus.BAD_REQUEST, setup_page("Şifre en az 6 karakter olmalı.", defaults))
            return
        if password != password_confirm:
            self.respond(HTTPStatus.BAD_REQUEST, setup_page("Şifreler birbiriyle eşleşmiyor.", defaults))
            return
        if db.get_user_by_username(username):
            self.respond(HTTPStatus.BAD_REQUEST, setup_page("Bu kullanıcı adı zaten kullanılıyor.", defaults))
            return
        user_id = db.create_user(
            username=username,
            password=password,
            full_name=full_name,
            email=email,
            role_codes=["admin"],
        )
        self.redirect("/login?setup=done")

    def _can_post_to(self, path: str) -> bool:
        permissions = getattr(self, "current_permissions", set())
        permission_map = {
            "/tasks": "tasks.create",
            "/tasks/toggle": "tasks.edit",
            "/tasks/update": "tasks.edit",
            "/tasks/delete": "tasks.delete",
            "/tasks/requests/approve": "tasks.edit",
            "/tasks/requests/reject": "tasks.edit",
            "/tasks/requests/history/delete": "tasks.view",
            "/tasks/requests/history/clear": "tasks.view",
            "/meetings": "meetings.create",
            "/meetings/update": "meetings.edit",
            "/meetings/delete": "meetings.delete",
            "/meetings/attachments": "attachments.upload",
            "/meeting-templates": "roles.manage",
            "/meeting-templates/delete": "roles.manage",
            "/meetings/task": "tasks.create",
            "/documents": "documents.create",
            "/documents/update": "documents.edit",
            "/documents/delete": "documents.delete",
            "/documents/toggle": "documents.edit",
            "/documents/attachments": "attachments.upload",
            "/documents/requests/approve": "documents.edit",
            "/documents/requests/reject": "documents.edit",
            "/documents/requests/history/delete": "documents.view",
            "/documents/requests/history/clear": "documents.view",
            "/recurring-documents": "documents.create",
            "/suppliers": "suppliers.create",
            "/suppliers/update": "suppliers.edit",
            "/suppliers/delete": "suppliers.delete",
            "/supplier-notes": "suppliers.edit",
            "/supplier-notes/update": "suppliers.edit",
            "/supplier-notes/delete": "suppliers.edit",
            "/events": "events.create",
            "/events/update": "events.edit",
            "/events/delete": "events.delete",
            "/users": "users.manage",
            "/users/update": "users.manage",
            "/users/toggle-active": "users.manage",
            "/companies": "roles.manage",
            "/companies/update": "roles.manage",
            "/companies/delete": "roles.manage",
            "/branches": "roles.manage",
            "/branches/update": "roles.manage",
            "/branches/delete": "roles.manage",
            "/backup-settings/create": "roles.manage",
            "/file-settings": "roles.manage",
            "/permissions": "roles.manage",
            "/attachments/delete": "attachments.delete",
        }
        required = permission_map.get(path)
        return required is None or required in permissions

    def log_message(self, format: str, *args) -> None:
        return


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    db.init_db()
    server = ThreadingHTTPServer((host, port), MyNotesHandler)
    print(f"Pelixi çalışıyor: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _parse_multipart_form_data(content_type: str, raw_bytes: bytes) -> tuple[dict[str, list[str]], dict[str, dict]]:
    boundary_token = "boundary="
    if boundary_token not in content_type:
        return {}, {}
    boundary = content_type.split(boundary_token, 1)[1].strip().strip('"')
    delimiter = ("--" + boundary).encode()
    parsed: dict[str, list[str]] = {}
    files: dict[str, dict] = {}
    for part in raw_bytes.split(delimiter):
        part = part.strip()
        if not part or part == b"--":
            continue
        if part.startswith(b"\r\n"):
            part = part[2:]
        header_bytes, separator, body = part.partition(b"\r\n\r\n")
        if not separator:
            continue
        body = body[:-2] if body.endswith(b"\r\n") else body
        headers: dict[str, str] = {}
        for line in header_bytes.decode("utf-8", errors="ignore").split("\r\n"):
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
        disposition = headers.get("content-disposition", "")
        if not disposition:
            continue
        disposition_parts = [segment.strip() for segment in disposition.split(";")]
        params: dict[str, str] = {}
        for segment in disposition_parts[1:]:
            if "=" not in segment:
                continue
            key, value = segment.split("=", 1)
            params[key.strip()] = value.strip().strip('"')
        field_name = params.get("name")
        if not field_name:
            continue
        filename = params.get("filename", "")
        if filename:
            files[field_name] = {
                "filename": filename,
                "content_type": headers.get("content-type", "application/octet-stream"),
                "content": body,
            }
            continue
        parsed.setdefault(field_name, []).append(body.decode("utf-8", errors="ignore"))
    return parsed, files


def _sanitize_filename(filename: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {".", "-", "_"} else "_" for ch in filename.strip())
    return safe or "dosya.bin"


def _first_feedback_value(values: list[str], mapping: dict[str, str]) -> str:
    for value in values:
        if value in mapping:
            return mapping[value]
    return ""


def _build_task_visibility_clause(current_user_id: int, is_admin: bool) -> tuple[str, tuple]:
    if is_admin:
        return "", ()
    return (
        "AND (tasks.owner_user_id = ? "
        "OR EXISTS (SELECT 1 FROM record_user_shares WHERE module_name = 'tasks' AND record_id = tasks.id AND user_id = ?) "
        "OR EXISTS (SELECT 1 FROM record_role_shares "
        "INNER JOIN user_roles ON user_roles.role_id = record_role_shares.role_id "
        "WHERE record_role_shares.module_name = 'tasks' AND record_role_shares.record_id = tasks.id AND user_roles.user_id = ?)) ",
        (current_user_id, current_user_id, current_user_id),
    )


def _build_record_visibility_where(module_name: str, current_user_id: int | None, is_admin: bool, table_name: str) -> tuple[str, tuple]:
    if is_admin or current_user_id is None:
        return "", ()
    return (
        " WHERE (owner_user_id = ? "
        f"OR EXISTS (SELECT 1 FROM record_user_shares WHERE module_name = ? AND record_id = {table_name}.id AND user_id = ?) "
        f"OR EXISTS (SELECT 1 FROM record_role_shares "
        f"INNER JOIN user_roles ON user_roles.role_id = record_role_shares.role_id "
        f"WHERE record_role_shares.module_name = ? AND record_role_shares.record_id = {table_name}.id AND user_roles.user_id = ?))",
        (current_user_id, module_name, current_user_id, module_name, current_user_id),
    )


def _build_tasks_query(active_filter: str, current_user_id: int, is_admin: bool) -> tuple[str, tuple]:
    base_query = (
        "SELECT * FROM tasks WHERE status != 'completed' "
    )
    visibility_clause, visibility_params = _build_task_visibility_clause(current_user_id, is_admin)
    filter_clauses = {
        "today": "AND due_date = date('now', 'localtime') ",
        "upcoming": "AND due_date > date('now', 'localtime') AND due_date <= date('now', 'localtime', '+7 day') ",
        "overdue": "AND due_date != '' AND due_date < date('now', 'localtime') ",
        "no_date": "AND (due_date IS NULL OR due_date = '') ",
    }
    ordering = (
        "ORDER BY CASE priority "
        "WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, "
        "CASE WHEN due_date IS NULL OR due_date = '' THEN 1 ELSE 0 END, due_date ASC, updated_at DESC"
    )
    return base_query + visibility_clause + filter_clauses.get(active_filter, "") + ordering, visibility_params


def _build_completed_tasks_query(current_user_id: int, is_admin: bool) -> tuple[str, tuple]:
    visibility_clause, visibility_params = _build_task_visibility_clause(current_user_id, is_admin)
    query = (
        "SELECT * FROM tasks WHERE status = 'completed' "
        + visibility_clause +
        "ORDER BY CASE WHEN completed_at IS NULL OR completed_at = '' THEN 1 ELSE 0 END, completed_at DESC, updated_at DESC"
    )
    return query, visibility_params


def _can_manage_task_directly(task_row, current_user_id: int, is_admin: bool) -> bool:
    if is_admin:
        return True
    owner_user_id = task_row["owner_user_id"]
    return bool(owner_user_id and int(owner_user_id) == current_user_id)


def _can_request_task_change(task_row, current_user_id: int) -> bool:
    owner_user_id = task_row["owner_user_id"]
    if owner_user_id and int(owner_user_id) == current_user_id:
        return True
    share_ids = db.get_record_user_share_ids("tasks", int(task_row["id"]))
    if current_user_id in share_ids:
        return True
    record_role_ids = set(db.get_record_role_share_ids("tasks", int(task_row["id"])))
    user_role_ids = {int(role["id"]) for role in db.list_roles() if role["code"] in db.get_user_role_codes(current_user_id)}
    return bool(record_role_ids.intersection(user_role_ids))


def _fetch_document_row(document_id: int, document_kind: str):
    if document_kind == "recurring":
        return db.fetch_one("SELECT * FROM recurring_documents WHERE id = ?", (document_id,))
    return db.fetch_one("SELECT * FROM documents WHERE id = ?", (document_id,))


def _can_manage_document_directly(document_row, current_user_id: int, is_admin: bool) -> bool:
    if is_admin:
        return True
    owner_user_id = document_row["owner_user_id"]
    return bool(owner_user_id and int(owner_user_id) == current_user_id)


def _can_request_document_change(document_row, document_kind: str, current_user_id: int) -> bool:
    owner_user_id = document_row["owner_user_id"]
    if owner_user_id and int(owner_user_id) == current_user_id:
        return True
    module_name = "recurring_documents" if document_kind == "recurring" else "documents"
    share_ids = db.get_record_user_share_ids(module_name, int(document_row["id"]))
    if current_user_id in share_ids:
        return True
    record_role_ids = set(db.get_record_role_share_ids(module_name, int(document_row["id"])))
    user_role_ids = {int(role["id"]) for role in db.list_roles() if role["code"] in db.get_user_role_codes(current_user_id)}
    return bool(record_role_ids.intersection(user_role_ids))


def _delete_document_record(document_id: int, document_kind: str) -> None:
    module_name = "recurring_documents" if document_kind == "recurring" else "documents"
    table_name = "recurring_documents" if document_kind == "recurring" else "documents"
    db.execute("DELETE FROM record_user_shares WHERE module_name = ? AND record_id = ?", (module_name, document_id))
    db.execute("DELETE FROM record_role_shares WHERE module_name = ? AND record_id = ?", (module_name, document_id))
    db.execute(f"DELETE FROM {table_name} WHERE id = ?", (document_id,))


def _apply_document_update(
    document_id: int,
    source_kind: str,
    target_kind: str,
    title: str,
    frequency: str,
    next_due_date: str,
    description: str,
    actor_user_id: int,
    owner_user_id: int,
    share_user_ids: list[int],
    share_role_ids: list[int],
    visibility_type: str,
) -> None:
    if source_kind == "one_time" and target_kind == "one_time":
        db.execute(
            "UPDATE documents SET title = ?, description = ?, due_date = ?, responsible_person = ?, visibility_type = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (title, description, next_due_date, "", visibility_type, actor_user_id, document_id),
        )
        db.replace_record_user_shares("documents", document_id, share_user_ids)
        db.replace_record_role_shares("documents", document_id, share_role_ids)
        return
    if source_kind == "recurring" and target_kind == "recurring":
        db.execute(
            "UPDATE recurring_documents SET title = ?, frequency = ?, next_due_date = ?, responsible_person = ?, notes = ?, visibility_type = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (title, frequency, next_due_date, "", description, visibility_type, actor_user_id, document_id),
        )
        db.replace_record_user_shares("recurring_documents", document_id, share_user_ids)
        db.replace_record_role_shares("recurring_documents", document_id, share_role_ids)
        return
    if source_kind == "one_time" and target_kind == "recurring":
        db.execute("DELETE FROM record_user_shares WHERE module_name = 'documents' AND record_id = ?", (document_id,))
        db.execute("DELETE FROM record_role_shares WHERE module_name = 'documents' AND record_id = ?", (document_id,))
        db.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        new_id = db.execute_insert(
            "INSERT INTO recurring_documents (title, category, frequency, next_due_date, responsible_person, notes, owner_user_id, visibility_type, created_by, updated_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (title, "Genel", frequency, next_due_date, "", description, owner_user_id, visibility_type, actor_user_id, actor_user_id),
        )
        db.replace_record_user_shares("recurring_documents", new_id, share_user_ids)
        db.replace_record_role_shares("recurring_documents", new_id, share_role_ids)
        return
    if source_kind == "recurring" and target_kind == "one_time":
        db.execute("DELETE FROM record_user_shares WHERE module_name = 'recurring_documents' AND record_id = ?", (document_id,))
        db.execute("DELETE FROM record_role_shares WHERE module_name = 'recurring_documents' AND record_id = ?", (document_id,))
        db.execute("DELETE FROM recurring_documents WHERE id = ?", (document_id,))
        new_id = db.execute_insert(
            "INSERT INTO documents (title, institution, document_type, description, status, due_date, responsible_person, owner_user_id, visibility_type, created_by, updated_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (title, "", "Genel Evrak", description, "waiting", next_due_date, "", owner_user_id, visibility_type, actor_user_id, actor_user_id),
        )
        db.replace_record_user_shares("documents", new_id, share_user_ids)
        db.replace_record_role_shares("documents", new_id, share_role_ids)


def _build_outgoing_task_request_map(rows: list, user_map: dict[int, str]) -> dict[int, dict]:
    request_map: dict[int, dict] = {}
    for row in rows:
        task_id = int(row["task_id"])
        owner_name = row["owner_full_name"] or row["owner_username"] or user_map.get(int(row["owner_user_id"]), "Görev sahibi")
        existing = request_map.get(task_id)
        created_at = row["created_at"] or ""
        entry = {
            "request_id": int(row["id"]),
            "task_id": task_id,
            "request_type": row["request_type"],
            "owner_name": owner_name,
            "created_at": created_at,
        }
        if not existing or created_at >= existing.get("created_at", ""):
            request_map[task_id] = entry
    return request_map


def _attach_task_request_state(item, outgoing_request_map: dict[int, dict]) -> dict:
    task = dict(item)
    pending_request = outgoing_request_map.get(int(task["id"]))
    task["_pending_request"] = pending_request or {}
    task["_pending_request_type"] = pending_request.get("request_type", "") if pending_request else ""
    task["_pending_request_owner"] = pending_request.get("owner_name", "") if pending_request else ""
    return task


def _format_task_change_request(row, user_map: dict[int, str]) -> dict:
    requester_name = row["requester_full_name"] or row["requester_username"] or user_map.get(int(row["requester_user_id"]), "Kullanıcı")
    task_title = row["task_title"] or "Görev"
    request_type = row["request_type"] or "update"
    action_label = "düzenleme" if request_type == "update" else "silme"
    payload = {}
    try:
        payload = json.loads(row["payload"] or "{}")
    except json.JSONDecodeError:
        payload = {}
    detail = payload.get("title") if request_type == "update" else task_title
    summary = _build_task_request_summary(request_type, payload, task_title)
    return {
        "id": int(row["id"]),
        "task_id": int(row["task_id"]),
        "requester_name": requester_name,
        "task_title": task_title,
        "request_type": request_type,
        "action_label": action_label,
        "detail": detail or task_title,
        "summary": summary,
        "created_at": row["created_at"] or "",
    }


def _format_task_change_history(row, current_user_id: int, user_map: dict[int, str]) -> dict:
    requester_name = row["requester_full_name"] or row["requester_username"] or user_map.get(int(row["requester_user_id"]), "Kullanıcı")
    owner_name = row["owner_full_name"] or row["owner_username"] or user_map.get(int(row["owner_user_id"]), "Görev sahibi")
    resolver_name = row["resolver_full_name"] or row["resolver_username"] or ""
    role_label = "Giden" if int(row["requester_user_id"]) == current_user_id else "Gelen"
    request_label = "Düzenleme" if row["request_type"] == "update" else "Silme"
    status_value = row["status"] or "pending"
    status_label_map = {"pending": "Bekliyor", "approved": "Onaylandı", "rejected": "Reddedildi"}
    payload = {}
    try:
        payload = json.loads(row["payload"] or "{}")
    except json.JSONDecodeError:
        payload = {}
    detail = f"{requester_name} -> {owner_name}"
    if status_value in {"approved", "rejected"} and resolver_name:
        detail += f" • Karar: {resolver_name}"
    summary = _build_task_request_summary(row["request_type"] or "update", payload, row["task_title"] or "Görev")
    return {
        "id": int(row["id"]),
        "task_title": row["task_title"] or "Görev",
        "role_label": role_label,
        "request_label": request_label,
        "status": status_value,
        "status_label": status_label_map.get(status_value, status_value),
        "detail": detail,
        "summary": summary,
        "updated_at": row["updated_at"] or row["created_at"] or "",
        "can_delete": status_value != "pending",
    }


def _build_task_request_summary(request_type: str, payload: dict, fallback_title: str) -> str:
    if request_type == "delete":
        return "Görevin silinmesi istendi."

    changes: list[str] = []
    title = (payload.get("title") or "").strip()
    responsible = (payload.get("responsible_person") or "").strip()
    description = (payload.get("description") or "").strip()
    priority = (payload.get("priority") or "").strip()
    due_date = (payload.get("due_date") or "").strip()

    if title and title != fallback_title:
        changes.append(f"Başlık: {title}")
    if responsible:
        changes.append(f"Sorumlu: {responsible}")
    if description:
        changes.append(f"Açıklama: {description[:36]}{'...' if len(description) > 36 else ''}")
    if priority:
        priority_map = {
            "low": "Düşük",
            "medium": "Orta",
            "high": "Yüksek",
            "critical": "Kritik",
        }
        changes.append(f"Öncelik: {priority_map.get(priority, priority)}")
    if due_date:
        changes.append(f"Tarih: {_format_date_label(due_date)}")

    if not changes:
        return "Görev bilgileri güncellenmek istendi."
    return " • ".join(changes[:3])


def _build_outgoing_document_request_map(rows: list, user_map: dict[int, str]) -> dict[tuple[str, int], dict]:
    request_map: dict[tuple[str, int], dict] = {}
    for row in rows:
        key = (row["document_kind"], int(row["document_id"]))
        owner_name = row["owner_full_name"] or row["owner_username"] or user_map.get(int(row["owner_user_id"]), "Evrak sahibi")
        existing = request_map.get(key)
        created_at = row["created_at"] or ""
        entry = {
            "request_id": int(row["id"]),
            "document_id": int(row["document_id"]),
            "document_kind": row["document_kind"],
            "request_type": row["request_type"],
            "owner_name": owner_name,
            "created_at": created_at,
        }
        if not existing or created_at >= existing.get("created_at", ""):
            request_map[key] = entry
    return request_map


def _attach_document_request_state(item, outgoing_request_map: dict[tuple[str, int], dict]) -> dict:
    document = dict(item)
    pending_request = outgoing_request_map.get((document["kind"], int(document["id"])))
    document["_pending_request"] = pending_request or {}
    document["_pending_request_type"] = pending_request.get("request_type", "") if pending_request else ""
    document["_pending_request_owner"] = pending_request.get("owner_name", "") if pending_request else ""
    return document


def _format_document_change_request(row, user_map: dict[int, str]) -> dict:
    requester_name = row["requester_full_name"] or row["requester_username"] or user_map.get(int(row["requester_user_id"]), "Kullanıcı")
    document_title = row["document_title"] or "Evrak"
    request_type = row["request_type"] or "update"
    action_label = "düzenleme" if request_type == "update" else "silme"
    payload = {}
    try:
        payload = json.loads(row["payload"] or "{}")
    except json.JSONDecodeError:
        payload = {}
    detail = payload.get("title") if request_type == "update" else document_title
    summary = _build_document_request_summary(request_type, payload, document_title)
    return {
        "id": int(row["id"]),
        "document_id": int(row["document_id"]),
        "document_kind": row["document_kind"],
        "requester_name": requester_name,
        "document_title": document_title,
        "request_type": request_type,
        "action_label": action_label,
        "detail": detail or document_title,
        "summary": summary,
        "created_at": row["created_at"] or "",
    }


def _format_document_change_history(row, current_user_id: int, user_map: dict[int, str]) -> dict:
    requester_name = row["requester_full_name"] or row["requester_username"] or user_map.get(int(row["requester_user_id"]), "Kullanıcı")
    owner_name = row["owner_full_name"] or row["owner_username"] or user_map.get(int(row["owner_user_id"]), "Evrak sahibi")
    resolver_name = row["resolver_full_name"] or row["resolver_username"] or ""
    role_label = "Giden" if int(row["requester_user_id"]) == current_user_id else "Gelen"
    request_label = "Düzenleme" if row["request_type"] == "update" else "Silme"
    status_value = row["status"] or "pending"
    status_label_map = {"pending": "Bekliyor", "approved": "Onaylandı", "rejected": "Reddedildi"}
    payload = {}
    try:
        payload = json.loads(row["payload"] or "{}")
    except json.JSONDecodeError:
        payload = {}
    detail = f"{requester_name} -> {owner_name}"
    if status_value in {"approved", "rejected"} and resolver_name:
        detail += f" • Karar: {resolver_name}"
    summary = _build_document_request_summary(row["request_type"] or "update", payload, row["document_title"] or "Evrak")
    return {
        "id": int(row["id"]),
        "document_title": row["document_title"] or "Evrak",
        "role_label": role_label,
        "request_label": request_label,
        "status": status_value,
        "status_label": status_label_map.get(status_value, status_value),
        "detail": detail,
        "summary": summary,
        "updated_at": row["updated_at"] or row["created_at"] or "",
        "can_delete": status_value != "pending",
    }


def _build_document_request_summary(request_type: str, payload: dict, fallback_title: str) -> str:
    if request_type == "delete":
        return "Evrak kaydının silinmesi istendi."
    changes: list[str] = []
    title = (payload.get("title") or "").strip()
    target_kind = (payload.get("target_kind") or "").strip()
    frequency = (payload.get("frequency") or "").strip()
    next_due_date = (payload.get("next_due_date") or "").strip()
    description = (payload.get("description") or "").strip()

    if title and title != fallback_title:
        changes.append(f"Başlık: {title}")
    if target_kind:
        kind_label = "Tekrarlı" if target_kind == "recurring" else "Tekrarsız"
        changes.append(f"Tür: {kind_label}")
    if target_kind == "recurring" and frequency:
        frequency_label = {
            "weekly": "Haftalık",
            "monthly": "Aylık",
            "quarterly": "3 Aylık",
            "semiannual": "6 Aylık",
            "yearly": "Yıllık",
            "custom": "Özel Periyot",
        }.get(frequency, frequency)
        changes.append(f"Periyot: {frequency_label}")
    if next_due_date:
        changes.append(f"Tarih: {_format_date_label(next_due_date)}")
    if description:
        changes.append(f"Açıklama: {description[:36]}{'...' if len(description) > 36 else ''}")
    if not changes:
        return "Evrak bilgileri güncellenmek istendi."
    return " • ".join(changes[:3])


def _build_dashboard_alerts(current_user_id: int, is_admin: bool, permissions: set[str]) -> list[dict]:
    alerts: list[dict] = []

    if "tasks.view" in permissions:
        overdue_query, overdue_params = _build_tasks_query("overdue", current_user_id, is_admin)
        overdue_tasks = db.fetch_all(overdue_query + " LIMIT 3", overdue_params)
        for row in overdue_tasks:
            alerts.append(
                {
                    "tone": "danger",
                    "title": "Geciken görev",
                    "detail": row["title"],
                    "meta": row["due_date"] or "-",
                }
            )

    if "documents.view" in permissions:
        active_document_items, _ = _build_document_items(current_user_id, is_admin)
        upcoming_docs = _filter_document_items(active_document_items, ["upcoming"])[:3]
        for row in upcoming_docs:
            alerts.append(
                {
                    "tone": "warn",
                    "title": "Yaklaşan evrak",
                    "detail": row["title"],
                    "meta": row["date_label"] or "-",
                }
            )

    if "events.view" in permissions:
        today_events = db.fetch_all(
            "SELECT title, event_date, end_date FROM events "
            "WHERE event_date <= date('now', 'localtime') "
            "AND COALESCE(NULLIF(end_date, ''), event_date) >= date('now', 'localtime') "
            "ORDER BY event_date ASC, title ASC LIMIT 3"
        )
        for row in today_events:
            alerts.append(
                {
                    "tone": "info",
                    "title": "Bugünkü etkinlik",
                    "detail": row["title"],
                    "meta": _format_date_range(row["event_date"], row["end_date"]),
                }
            )

    return alerts[:6]


def _build_notification_groups(current_user_id: int, is_admin: bool, permissions: set[str]) -> list[dict]:
    settings = db.get_notification_settings(current_user_id)
    active_user_map = {
        int(user["id"]): (user["full_name"] or user["username"] or "Kullanıcı")
        for user in db.list_active_users()
    }

    owner_requests = []
    if "tasks.view" in permissions:
        owner_requests = [_format_task_change_request(row, active_user_map) for row in db.list_pending_task_change_requests(current_user_id)]

    owner_document_requests = []
    if "documents.view" in permissions:
        owner_document_requests = [_format_document_change_request(row, active_user_map) for row in db.list_pending_document_change_requests(current_user_id)]

    approval_items = [
        {
            "title": f"{item['requester_name']} talep gönderdi",
            "detail": f"{item['task_title']} · {item['action_label']}",
            "meta": item.get("summary", ""),
            "href": "/tasks",
            "action": "İncele",
            "tone": "approval",
        }
        for item in owner_requests
    ]
    approval_items.extend(
        {
            "title": f"{item['requester_name']} talep gönderdi",
            "detail": f"{item['document_title']} · {item['action_label']}",
            "meta": item.get("summary", ""),
            "href": "/documents",
            "action": "İncele",
            "tone": "approval",
        }
        for item in owner_document_requests
    )

    outgoing_items = []
    if "tasks.view" in permissions:
        outgoing_rows = db.list_outgoing_pending_task_change_requests(current_user_id)
        for row in outgoing_rows:
            owner_name = row["owner_full_name"] or row["owner_username"] or active_user_map.get(int(row["owner_user_id"]), "Görev sahibi")
            request_label = "Düzenleme" if row["request_type"] == "update" else "Silme"
            outgoing_items.append(
                {
                    "title": f"{request_label} onayı bekliyor",
                    "detail": row["task_title"] or "Görev",
                    "meta": f"Onay: {owner_name}",
                    "href": "/tasks",
                    "action": "Görevlere Git",
                    "tone": "info",
                }
            )
    if "documents.view" in permissions:
        outgoing_document_rows = db.list_outgoing_pending_document_change_requests(current_user_id)
        for row in outgoing_document_rows:
            owner_name = row["owner_full_name"] or row["owner_username"] or active_user_map.get(int(row["owner_user_id"]), "Evrak sahibi")
            request_label = "Düzenleme" if row["request_type"] == "update" else "Silme"
            outgoing_items.append(
                {
                    "title": f"{request_label} onayı bekliyor",
                    "detail": row["document_title"] or "Evrak",
                    "meta": f"Onay: {owner_name}",
                    "href": "/documents",
                    "action": "Evraklara Git",
                    "tone": "info",
                }
            )

    task_items = []
    if "tasks.view" in permissions:
        overdue_tasks = db.fetch_all(*_build_tasks_query("overdue", current_user_id, is_admin))
        upcoming_tasks = db.fetch_all(*_build_tasks_query("upcoming", current_user_id, is_admin))
        for row in overdue_tasks[:5]:
            task_items.append(
                {
                    "title": "Geciken görev",
                    "detail": row["title"],
                    "meta": f"Son tarih: {_format_date_label(row['due_date'])}",
                    "href": "/tasks?filter=overdue",
                    "action": "Aç",
                    "tone": "danger",
                }
            )
        for row in upcoming_tasks[:5]:
            task_items.append(
                {
                    "title": "Yaklaşan görev",
                    "detail": row["title"],
                    "meta": f"Son tarih: {_format_date_label(row['due_date'])}",
                    "href": "/tasks?filter=upcoming",
                    "action": "Aç",
                    "tone": "warn",
                }
            )

    document_items = []
    if "documents.view" in permissions:
        active_document_items, _ = _build_document_items(current_user_id, is_admin)
        overdue_docs = _filter_document_items(active_document_items, ["overdue"])[:5]
        upcoming_docs = _filter_document_items(active_document_items, ["upcoming"])[:5]
        for row in overdue_docs:
            document_items.append(
                {
                    "title": "Geciken evrak",
                    "detail": row["title"],
                    "meta": f"Tarih: {row['date_label']}",
                    "href": "/documents?filter=overdue",
                    "action": "Aç",
                    "tone": "danger",
                }
            )
        for row in upcoming_docs:
            document_items.append(
                {
                    "title": "Yaklaşan evrak",
                    "detail": row["title"],
                    "meta": f"Tarih: {row['date_label']}",
                    "href": "/documents?filter=upcoming",
                    "action": "Aç",
                    "tone": "warn",
                }
            )

    event_items = []
    if "events.view" in permissions:
        event_rows = db.fetch_all(
            "SELECT * FROM events "
            "WHERE event_date <= date('now', 'localtime', '+7 days') "
            "AND COALESCE(NULLIF(end_date, ''), event_date) >= date('now', 'localtime') "
            "ORDER BY event_date ASC, title ASC LIMIT 8"
        )
        event_items = [
            {
                "title": "Yaklaşan etkinlik",
                "detail": row["title"],
                "meta": _format_date_range(row["event_date"], row["end_date"]),
                "href": "/events",
                "action": "Takvim",
                "tone": "info",
            }
            for row in event_rows
        ]

    groups = []
    if int(settings.get("approval_items", 1)):
        groups.append({"title": "Onay Bekleyenler", "tone": "approval", "items": approval_items})
    if int(settings.get("outgoing_items", 1)):
        groups.append({"title": "Gönderdiğiniz Talepler", "tone": "info", "items": outgoing_items})
    if int(settings.get("task_alerts", 1)):
        groups.append({"title": "Görev Uyarıları", "tone": "warn", "items": task_items[:8]})
    if int(settings.get("document_alerts", 1)):
        groups.append({"title": "Evrak Uyarıları", "tone": "danger", "items": document_items[:8]})
    if int(settings.get("event_reminders", 1)):
        groups.append({"title": "Etkinlik Hatırlatmaları", "tone": "info", "items": event_items})
    return [group for group in groups if group["items"]]


def _build_document_items(current_user_id: int | None = None, is_admin: bool = False) -> tuple[list[dict], list[dict]]:
    active_items: list[dict] = []
    completed_items: list[dict] = []
    document_where, document_params = _build_record_visibility_where("documents", current_user_id, is_admin, "documents")
    recurring_where, recurring_params = _build_record_visibility_where("recurring_documents", current_user_id, is_admin, "recurring_documents")
    for row in db.fetch_all("SELECT * FROM documents" + document_where, document_params):
        target = completed_items if row["status"] == "submitted" else active_items
        target.append(
            {
                "id": row["id"],
                "kind": "one_time",
                "kind_label": "Tek Seferlik",
                "title": row["title"],
                "frequency": "one_time",
                "frequency_label": "Tek Seferlik",
                "date_raw": row["due_date"] or "",
                "date_label": _format_date_label(row["due_date"]),
                "description": row["description"] or "",
                "responsible_person": row["responsible_person"] or "",
                "owner_user_id": row["owner_user_id"],
                "visibility_type": row["visibility_type"] or "private",
                "is_done": row["status"] == "submitted",
                "completed_label": _format_datetime_label(row["submitted_at"]),
                "last_completed_label": _format_datetime_label(row["submitted_at"]),
            }
        )
    frequency_labels = {
        "weekly": "Haftalık",
        "monthly": "Aylık",
        "quarterly": "3 Aylık",
        "semiannual": "6 Aylık",
        "yearly": "Yıllık",
        "custom": "Özel Periyot",
    }
    recurring_query = "SELECT * FROM recurring_documents WHERE is_active = 1" + recurring_where.replace(" WHERE ", " AND ", 1)
    for row in db.fetch_all(recurring_query, recurring_params):
        active_items.append(
            {
                "id": row["id"],
                "kind": "recurring",
                "kind_label": "Planlı",
                "title": row["title"],
                "frequency": row["frequency"],
                "frequency_label": frequency_labels.get(row["frequency"], row["frequency"]),
                "date_raw": row["next_due_date"] or "",
                "date_label": _format_date_label(row["next_due_date"]),
                "notes": row["notes"] or "",
                "description": row["notes"] or "",
                "responsible_person": row["responsible_person"] or "",
                "owner_user_id": row["owner_user_id"],
                "visibility_type": row["visibility_type"] or "private",
                "is_done": False,
                "completed_label": _format_datetime_label(row["last_completed_at"]),
                "last_completed_label": _format_datetime_label(row["last_completed_at"]),
            }
        )
    active_items = sorted(
        active_items,
        key=lambda item: (
            item["date_raw"] == "",
            item["date_raw"] or "9999-12-31",
            item["title"].lower(),
        ),
    )
    completed_items = sorted(
        completed_items,
        key=lambda item: (
            item["completed_label"] == "-",
            item["completed_label"],
            item["title"].lower(),
        ),
        reverse=True,
    )
    return active_items, completed_items


def _filter_document_items(items: list[dict], active_filters: list[str]) -> list[dict]:
    if not active_filters:
        return items
    today = datetime.now().strftime("%Y-%m-%d")
    upcoming_limit = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    filtered = items
    for active_filter in active_filters:
        if active_filter == "today":
            filtered = [item for item in filtered if item["date_raw"] == today]
        elif active_filter == "upcoming":
            filtered = [item for item in filtered if item["date_raw"] and today < item["date_raw"] <= upcoming_limit]
        elif active_filter == "overdue":
            filtered = [item for item in filtered if item["date_raw"] and item["date_raw"] < today]
        elif active_filter == "recurring":
            filtered = [item for item in filtered if item["kind"] == "recurring"]
    return filtered


def _format_date_label(value: str) -> str:
    if not value:
        return "-"
    parts = value[:10].split("-")
    if len(parts) == 3:
        return f"{parts[2]}.{parts[1]}.{parts[0]}"
    return value


def _format_date_range(start_value: str | None, end_value: str | None) -> str:
    start_label = _format_date_label(start_value or "")
    end_raw = end_value or start_value or ""
    end_label = _format_date_label(end_raw)
    if not start_value:
        return "-"
    if not end_raw or end_raw == start_value:
        return start_label
    return f"{start_label} - {end_label}"


def _iter_event_days(start_value: str | None, end_value: str | None) -> list[str]:
    if not start_value:
        return []
    try:
        start_date = datetime.strptime(start_value[:10], "%Y-%m-%d")
    except ValueError:
        return []
    try:
        end_date = datetime.strptime((end_value or start_value)[:10], "%Y-%m-%d")
    except ValueError:
        end_date = start_date
    if end_date < start_date:
        end_date = start_date
    days: list[str] = []
    current = start_date
    while current <= end_date:
        days.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return days


def _merge_public_holidays(date_map: dict[str, list[dict[str, str]]], year: int) -> None:
    for holiday_date, holiday_name in _turkish_public_holidays(year):
        date_map.setdefault(holiday_date, [])
        date_map[holiday_date].insert(
            0,
            {
                "title": holiday_name,
                "level_label": "Resmi tatil",
                "time_range": "",
                "notes": "Resmi tatil",
                "is_holiday": True,
            },
        )


def _turkish_public_holidays(year: int) -> list[tuple[str, str]]:
    try:
        import holidays  # type: ignore

        tr_holidays = holidays.Turkey(years=year, language="tr")
        return sorted((day.strftime("%Y-%m-%d"), str(name)) for day, name in tr_holidays.items())
    except Exception:
        # Kütüphane yoksa uygulama çalışmaya devam etsin; en azından sabit milli tatiller gösterilir.
        return [
            (f"{year}-01-01", "Yılbaşı"),
            (f"{year}-04-23", "Ulusal Egemenlik ve Çocuk Bayramı"),
            (f"{year}-05-01", "Emek ve Dayanışma Günü"),
            (f"{year}-05-19", "Atatürk'ü Anma, Gençlik ve Spor Bayramı"),
            (f"{year}-07-15", "Demokrasi ve Milli Birlik Günü"),
            (f"{year}-08-30", "Zafer Bayramı"),
            (f"{year}-10-29", "Cumhuriyet Bayramı"),
        ]


def _format_datetime_label(value: str | None) -> str:
    if not value:
        return "-"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.strftime("%d.%m.%Y %H:%M")
        except ValueError:
            continue
    return value


def _advance_due_date(current_value: str, frequency: str, custom_interval_days: int | None) -> str:
    try:
        current_date = datetime.strptime((current_value or "")[:10], "%Y-%m-%d")
    except ValueError:
        current_date = datetime.now()

    if frequency == "weekly":
        next_date = current_date + timedelta(days=7)
    elif frequency == "monthly":
        next_date = _add_months(current_date, 1)
    elif frequency == "quarterly":
        next_date = _add_months(current_date, 3)
    elif frequency == "semiannual":
        next_date = _add_months(current_date, 6)
    elif frequency == "yearly":
        next_date = _add_months(current_date, 12)
    elif frequency == "custom" and custom_interval_days:
        next_date = current_date + timedelta(days=custom_interval_days)
    else:
        next_date = current_date
    return next_date.strftime("%Y-%m-%d")


def _add_months(source_date: datetime, months: int) -> datetime:
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1
    day = min(source_date.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return source_date.replace(year=year, month=month, day=day)


def _add_month_delta(source_date: datetime, delta: int) -> datetime:
    return _add_months(source_date, delta)


def _normalize_phone(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    digits = digits.lstrip("0")
    return digits[:10]


def _normalize_share_user_ids(values: list[str], current_user_id: int) -> list[int]:
    selected: list[int] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned.isdigit():
            continue
        user_id = int(cleaned)
        if user_id == current_user_id or user_id in selected:
            continue
        target_user = db.get_user_by_id(user_id)
        if target_user and bool(target_user["is_active"]):
            selected.append(user_id)
    return selected


def _normalize_share_role_ids(values: list[str]) -> list[int]:
    role_rows = db.list_roles()
    valid_role_ids = {int(role["id"]) for role in role_rows}
    selected: list[int] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned.isdigit():
            continue
        role_id = int(cleaned)
        if role_id not in valid_role_ids or role_id in selected:
            continue
        selected.append(role_id)
    return selected


def _attach_task_share_summary(item, user_map: dict[int, str], role_map: dict[int, str], current_user_id: int | None = None) -> dict:
    task = dict(item)
    share_ids = db.get_record_user_share_ids("tasks", int(task["id"]))
    share_role_rows = db.get_record_role_shares("tasks", int(task["id"]))
    share_names = [user_map[user_id] for user_id in share_ids if user_id in user_map]
    share_role_ids = [int(row["id"]) for row in share_role_rows]
    share_role_names = [row["name"] or role_map.get(int(row["id"]), "Rol") for row in share_role_rows]
    owner_user_id = task.get("owner_user_id")
    try:
        owner_user_id = int(owner_user_id) if owner_user_id not in (None, "") else None
    except (TypeError, ValueError):
        owner_user_id = None
    owner_name = user_map.get(owner_user_id, "") if owner_user_id else ""
    if share_names and share_role_names:
        summary = f"{len(share_names)} kişi • {len(share_role_names)} rol"
    elif share_names:
        summary = ", ".join(share_names[:2])
        if len(share_names) > 2:
            summary += f" +{len(share_names) - 2}"
    elif share_role_names:
        summary = ", ".join(share_role_names[:2])
        if len(share_role_names) > 2:
            summary += f" +{len(share_role_names) - 2}"
    else:
        summary = "-"
    task["_share_user_ids"] = share_ids
    task["_share_names"] = share_names
    task["_share_role_ids"] = share_role_ids
    task["_share_role_names"] = share_role_names
    task["_share_summary"] = summary
    task["_share_count"] = len(share_names)
    task["_share_role_count"] = len(share_role_names)
    tooltip_parts = []
    if share_names:
        tooltip_parts.append("Kişiler: " + ", ".join(share_names))
    if share_role_names:
        tooltip_parts.append("Roller: " + ", ".join(share_role_names))
    task["_share_tooltip"] = " • ".join(tooltip_parts) if tooltip_parts else "Yalnızca size özel"
    task["_owner_name"] = owner_name
    task["_shared_from"] = owner_name if current_user_id and owner_user_id and owner_user_id != current_user_id else ""
    return task


def _attach_document_share_summary(item, user_map: dict[int, str], role_map: dict[int, str], current_user_id: int | None = None) -> dict:
    document = dict(item)
    module_name = "recurring_documents" if document.get("kind") == "recurring" else "documents"
    share_ids = db.get_record_user_share_ids(module_name, int(document["id"]))
    share_role_rows = db.get_record_role_shares(module_name, int(document["id"]))
    share_names = [user_map[user_id] for user_id in share_ids if user_id in user_map]
    share_role_ids = [int(row["id"]) for row in share_role_rows]
    share_role_names = [row["name"] or role_map.get(int(row["id"]), "Rol") for row in share_role_rows]
    owner_user_id = document.get("owner_user_id")
    try:
        owner_user_id = int(owner_user_id) if owner_user_id not in (None, "") else None
    except (TypeError, ValueError):
        owner_user_id = None
    owner_name = user_map.get(owner_user_id, "") if owner_user_id else ""
    if share_names and share_role_names:
        summary = f"{len(share_names)} kişi • {len(share_role_names)} rol"
    elif share_names:
        summary = ", ".join(share_names[:2])
        if len(share_names) > 2:
            summary += f" +{len(share_names) - 2}"
    elif share_role_names:
        summary = ", ".join(share_role_names[:2])
        if len(share_role_names) > 2:
            summary += f" +{len(share_role_names) - 2}"
    else:
        summary = "-"
    document["_share_user_ids"] = share_ids
    document["_share_names"] = share_names
    document["_share_role_ids"] = share_role_ids
    document["_share_role_names"] = share_role_names
    document["_share_summary"] = summary
    document["_share_count"] = len(share_names)
    document["_share_role_count"] = len(share_role_names)
    tooltip_parts = []
    if share_names:
        tooltip_parts.append("Kişiler: " + ", ".join(share_names))
    if share_role_names:
        tooltip_parts.append("Roller: " + ", ".join(share_role_names))
    document["_share_tooltip"] = " • ".join(tooltip_parts) if tooltip_parts else "Yalnızca size özel"
    document["_owner_name"] = owner_name
    document["_shared_from"] = owner_name if current_user_id and owner_user_id and owner_user_id != current_user_id else ""
    return document


def _cleanup_supplier_phone() -> None:
    rows = db.fetch_all("SELECT id, phone FROM suppliers")
    for row in rows:
        normalized = _normalize_phone(row["phone"] or "")
        if normalized != (row["phone"] or ""):
            db.execute(
                "UPDATE suppliers SET phone = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (normalized, int(row["id"])),
            )


def _normalize_event_levels(values: list[str]) -> list[str]:
    valid_levels = ["Anasınıfı", "İlkokul", "Ortaokul", "Lise"]
    selected = []
    for value in values:
        cleaned = value.strip()
        if cleaned in valid_levels and cleaned not in selected:
            selected.append(cleaned)
    return selected or ["İlkokul"]


def _split_event_levels(value: str | None) -> list[str]:
    if not value:
        return ["İlkokul"]
    return _normalize_event_levels([part.strip() for part in value.split(",") if part.strip()])


def _join_form_lines(values: list[str]) -> str:
    cleaned = [value.strip() for value in values if value.strip()]
    return "\n".join(cleaned)


def _build_task_feedback(query: dict[str, list[str]]) -> dict[str, str]:
    error_code = query.get("error", [""])[0]
    info_code = query.get("info", [""])[0]
    errors = {
        "task_missing": "Görev bulunamadı.",
        "request_history_empty": "Silmek için en az bir geçmiş kaydı seçin.",
    }
    infos = {
        "request_sent": "İşlem isteği görev sahibine gönderildi. Onaylandığında uygulanacak.",
        "request_approved": "Talep onaylandı ve işlem uygulandı.",
        "request_rejected": "Talep reddedildi.",
        "request_history_deleted": "Seçilen geçmiş kayıtları kaldırıldı.",
        "request_history_cleared": "Sonuçlanan talep geçmişi temizlendi.",
        "task_updated": "Görev güncellendi.",
        "task_deleted": "Görev silindi.",
    }
    if error_code in errors:
        return {"error": errors[error_code]}
    if info_code in infos:
        return {"info": infos[info_code]}
    return {}


def _build_document_feedback(query: dict[str, list[str]]) -> dict[str, str]:
    error_code = query.get("error", [""])[0]
    info_code = query.get("info", [""])[0]
    errors = {
        "document_missing": "Evrak bulunamadı.",
        "document_request_history_empty": "Silmek için en az bir geçmiş kaydı seçin.",
        "attachment_missing": "Dosya seçmeden gönderim yapılamaz.",
        "attachment_invalid_type": "Bu uzantı için dosya yükleme izni yok.",
        "attachment_too_large": "Dosya boyutu izin verilen sınırı aşıyor.",
    }
    infos = {
        "document_created": "Evrak kaydedildi.",
        "document_created_with_attachment": "Evrak kaydedildi, dosya eklendi.",
        "document_request_sent": "İşlem isteği evrak sahibine gönderildi. Onaylandığında uygulanacak.",
        "document_request_approved": "Talep onaylandı ve işlem uygulandı.",
        "document_request_rejected": "Talep reddedildi.",
        "document_request_history_deleted": "Seçilen geçmiş kayıtları kaldırıldı.",
        "document_request_history_cleared": "Sonuçlanan talep geçmişi temizlendi.",
        "document_updated": "Evrak güncellendi.",
        "document_deleted": "Evrak silindi.",
        "attachment_uploaded": "Dosya eklendi.",
        "attachment_deleted": "Dosya silindi.",
    }
    if error_code in errors:
        return {"error": errors[error_code]}
    if info_code in infos:
        return {"info": infos[info_code]}
    return {}


def _build_notification_settings_feedback(query: dict[str, list[str]]) -> dict[str, str]:
    info_code = query.get("info", [""])[0]
    infos = {
        "saved": "Bildirim ayarları kaydedildi.",
    }
    if info_code in infos:
        return {"info": infos[info_code]}
    return {}


def _build_backup_settings_feedback(query: dict[str, list[str]]) -> dict[str, str]:
    info_code = query.get("info", [""])[0]
    infos = {
        "created": "Yeni yedek oluşturuldu.",
    }
    if info_code in infos:
        return {"info": infos[info_code]}
    return {}


def _build_file_settings_feedback(query: dict[str, list[str]]) -> dict[str, str]:
    info_code = query.get("info", [""])[0]
    infos = {
        "saved": "Dosya ayarları kaydedildi.",
    }
    if info_code in infos:
        return {"info": infos[info_code]}
    return {}


def _build_audit_logs_feedback(query: dict[str, list[str]]) -> dict[str, str]:
    return {}


def _format_file_size(size_bytes: int) -> str:
    value = float(size_bytes)
    units = ["B", "KB", "MB", "GB"]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{int(size_bytes)} B"


def _normalize_extension_list(raw_value: str) -> str:
    parts = [part.strip().lower() for part in str(raw_value or "").split(",")]
    cleaned: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if not part:
            continue
        normalized = part if part.startswith(".") else f".{part}"
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return ", ".join(cleaned)


def _format_extension_preview(raw_value: str) -> str:
    parts = [part.strip() for part in str(raw_value or "").split(",") if part.strip()]
    if not parts:
        return "-"
    if len(parts) <= 3:
        return " • ".join(parts)
    return " • ".join(parts[:3]) + f" +{len(parts) - 3}"


def _validate_uploaded_file(upload: dict, settings: dict) -> str | None:
    file_name = str(upload.get("filename") or "").strip()
    content = upload.get("content") or b""
    if not file_name or not content:
        return "attachment_missing"
    allowed_extensions = {
        part.strip().lower()
        for part in str(settings.get("allowed_extensions", "")).split(",")
        if part.strip()
    }
    file_extension = Path(file_name).suffix.lower()
    if allowed_extensions and file_extension not in allowed_extensions:
        return "attachment_invalid_type"
    try:
        max_size_bytes = max(1, int(settings.get("max_file_size_mb", 10))) * 1024 * 1024
    except (TypeError, ValueError):
        max_size_bytes = 10 * 1024 * 1024
    if len(content) > max_size_bytes:
        return "attachment_too_large"
    return None


def _build_user_feedback(query: dict[str, list[str]]) -> dict[str, str]:
    error_code = query.get("error", [""])[0]
    info_code = query.get("info", [""])[0]
    errors = {
        "missing": "Ad soyad, kullanıcı adı ve şifre zorunludur.",
        "update_missing": "Güncelleme için gerekli alanları doldurun.",
        "password_short": "Şifre en az 6 karakter olmalı.",
        "username_exists": "Bu kullanıcı adı zaten kullanılıyor.",
        "email_exists": "Bu e-posta başka bir kullanıcıda kayıtlı.",
        "toggle_denied": "Bu kullanıcı için durum değişikliği yapılamadı.",
    }
    infos = {
        "user_created": "Kullanıcı başarıyla eklendi.",
        "user_updated": "Kullanıcı bilgileri güncellendi.",
        "user_toggled": "Kullanıcı durumu güncellendi.",
    }
    if error_code in errors:
        return {"error": errors[error_code]}
    if info_code in infos:
        return {"info": infos[info_code]}
    return {}


def _build_permission_feedback(query: dict[str, list[str]]) -> dict[str, str]:
    error_code = query.get("error", [""])[0]
    info_code = query.get("info", [""])[0]
    errors = {
        "missing_role": "Önce bir rol seçin.",
    }
    infos = {
        "permissions_saved": "Rol yetkileri güncellendi.",
    }
    if error_code in errors:
        return {"error": errors[error_code]}
    if info_code in infos:
        return {"info": infos[info_code]}
    return {}


def _build_meeting_template_feedback(query: dict[str, list[str]]) -> dict[str, str]:
    error_code = query.get("error", [""])[0]
    info_code = query.get("info", [""])[0]
    errors = {
        "template_missing": "Başlık alanını boş bırakamazsınız.",
    }
    infos = {
        "template_saved": "Başlık eklendi.",
        "template_deleted": "Başlık silindi.",
    }
    if error_code in errors:
        return {"error": errors[error_code]}
    if info_code in infos:
        return {"info": infos[info_code]}
    return {}


def _build_roles_feedback(query: dict[str, list[str]]) -> dict[str, str]:
    error_code = query.get("error", [""])[0]
    info_code = query.get("info", [""])[0]
    errors = {
        "role_missing": "Rol adı zorunludur.",
    }
    infos = {
        "role_saved": "Rol eklendi.",
    }
    if error_code in errors:
        return {"error": errors[error_code]}
    if info_code in infos:
        return {"info": infos[info_code]}
    return {}


def _build_company_feedback(query: dict[str, list[str]]) -> dict[str, str]:
    error_code = query.get("error", [""])[0]
    info_code = query.get("info", [""])[0]
    errors = {
        "company_missing": "Firma adı ve kısa kod zorunludur.",
    }
    infos = {
        "company_saved": "Firma eklendi.",
    }
    if error_code in errors:
        return {"error": errors[error_code]}
    if info_code in infos:
        return {"info": infos[info_code]}
    return {}


def _build_branch_feedback(query: dict[str, list[str]]) -> dict[str, str]:
    error_code = query.get("error", [""])[0]
    info_code = query.get("info", [""])[0]
    errors = {
        "branch_missing": "Şube için firma, ad ve kısa kod zorunludur.",
    }
    infos = {
        "branch_saved": "Şube eklendi.",
    }
    if error_code in errors:
        return {"error": errors[error_code]}
    if info_code in infos:
        return {"info": infos[info_code]}
    return {}


def _decorate_role_row(row):
    item = dict(row)
    item["is_system"] = 1 if str(item.get("code") or "") in db.SYSTEM_ROLE_CODES else 0
    return item


def _slugify_role_code(value: str) -> str:
    replacements = str.maketrans({
        "ç": "c", "Ç": "c",
        "ğ": "g", "Ğ": "g",
        "ı": "i", "İ": "i",
        "ö": "o", "Ö": "o",
        "ş": "s", "Ş": "s",
        "ü": "u", "Ü": "u",
    })
    cleaned = value.translate(replacements).lower()
    normalized = []
    last_was_sep = False
    for char in cleaned:
        if char.isalnum():
            normalized.append(char)
            last_was_sep = False
        elif not last_was_sep:
            normalized.append("_")
            last_was_sep = True
    return "".join(normalized).strip("_")
