from __future__ import annotations

import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from datetime import datetime, timedelta

from app import db
from app.views import (
    dashboard_page,
    documents_dashboard_page_filtered,
    events_page,
    meetings_workspace_page_v3 as meetings_dashboard_page,
    calendar_nav_bar,
    quick_event_form,
    render_event_calendar,
    render_event_year_calendar,
    quick_document_form,
    suppliers_page as suppliers_dashboard_page,
    not_found_page,
    search_results_page,
    tasks_page,
    module_page,
    document_form,
    render_document_item,
    render_supplier_item,
)


if getattr(sys, "frozen", False):
    STATIC_DIR = Path(getattr(sys, "_MEIPASS", Path(os.getcwd()))) / "static"
else:
    STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


class MyNotesHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path.startswith("/static/"):
            self.serve_static(parsed.path)
            return

        routes = {
            "/": self.dashboard,
            "/search": lambda: self.search_page(query),
            "/tasks": lambda: self.tasks_page(query),
            "/meetings": lambda: self.meetings_page(query),
            "/documents": lambda: self.documents_page(query),
            "/events": lambda: self.events_page(query),
            "/suppliers": lambda: self.suppliers_page(query),
        }
        handler = routes.get(parsed.path)
        if handler is None:
            self.respond(HTTPStatus.NOT_FOUND, not_found_page())
            return
        handler()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length).decode("utf-8")
        parsed_body = parse_qs(raw_body)
        form_data = {key: values[0] for key, values in parsed_body.items()}

        if parsed.path == "/tasks":
            db.execute(
                "INSERT INTO tasks (title, responsible_person, description, category, priority, status, due_date) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    form_data.get("title", "").strip(),
                    form_data.get("responsible_person", "").strip(),
                    "",
                    "Genel",
                    form_data.get("priority", "medium"),
                    "pending",
                    form_data.get("due_date", "").strip(),
                ),
            )
        elif parsed.path == "/tasks/toggle":
            task_id = form_data.get("id", "").strip()
            next_status = form_data.get("next_status", "completed").strip()
            if task_id.isdigit() and next_status in {"pending", "completed"}:
                if next_status == "completed":
                    db.execute(
                        "UPDATE tasks SET status = ?, completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
                        "WHERE id = ?",
                        (next_status, int(task_id)),
                    )
                else:
                    db.execute(
                        "UPDATE tasks SET status = ?, completed_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (next_status, int(task_id)),
                    )
        elif parsed.path == "/tasks/update":
            task_id = form_data.get("id", "").strip()
            if task_id.isdigit():
                db.execute(
                    "UPDATE tasks SET title = ?, responsible_person = ?, priority = ?, due_date = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (
                        form_data.get("title", "").strip(),
                        form_data.get("responsible_person", "").strip(),
                        form_data.get("priority", "medium").strip(),
                        form_data.get("due_date", "").strip(),
                        int(task_id),
                    ),
                )
        elif parsed.path == "/tasks/delete":
            task_id = form_data.get("id", "").strip()
            if task_id.isdigit():
                db.execute("DELETE FROM tasks WHERE id = ?", (int(task_id),))
        elif parsed.path == "/meetings":
            title = form_data.get("title", "").strip()
            if title == "__custom__":
                title = form_data.get("custom_title", "").strip()
            agenda = _join_form_lines(parsed_body.get("agenda_item", []))
            decisions = _join_form_lines(parsed_body.get("decision_item", []))
            meeting_id = db.execute_insert(
                "INSERT INTO meeting_notes (title, meeting_type, meeting_date, participants, agenda, notes, decisions, follow_up_items) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    title,
                    "",
                    form_data.get("meeting_date", "").strip(),
                    "",
                    agenda,
                    form_data.get("notes", "").strip(),
                    decisions,
                    "",
                ),
            )
        elif parsed.path == "/meetings/update":
            meeting_id = form_data.get("id", "").strip()
            if meeting_id.isdigit():
                title = form_data.get("title", "").strip()
                if title == "__custom__":
                    title = form_data.get("custom_title", "").strip()
                agenda = _join_form_lines(parsed_body.get("agenda_item", []))
                decisions = _join_form_lines(parsed_body.get("decision_item", []))
                db.execute(
                    "UPDATE meeting_notes SET title = ?, meeting_date = ?, agenda = ?, notes = ?, decisions = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (
                        title,
                        form_data.get("meeting_date", "").strip(),
                        agenda,
                        form_data.get("notes", "").strip(),
                        decisions,
                        int(meeting_id),
                    ),
                )
        elif parsed.path == "/meetings/delete":
            meeting_id = form_data.get("id", "").strip()
            if meeting_id.isdigit():
                db.execute("DELETE FROM meeting_notes WHERE id = ?", (int(meeting_id),))
        elif parsed.path == "/meeting-templates":
            title = form_data.get("title", "").strip()
            if title:
                current_max = db.fetch_one("SELECT COALESCE(MAX(sort_order), 0) AS value FROM meeting_templates")
                next_order = int(current_max["value"]) + 1 if current_max else 1
                db.execute(
                    "INSERT OR IGNORE INTO meeting_templates (title, sort_order) VALUES (?, ?)",
                    (title, next_order),
                )
        elif parsed.path == "/meeting-templates/delete":
            template_id = form_data.get("id", "").strip()
            if template_id.isdigit():
                db.execute("DELETE FROM meeting_templates WHERE id = ?", (int(template_id),))
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
        elif parsed.path == "/documents":
            kind = form_data.get("kind", "one_time").strip()
            frequency = form_data.get("frequency", "monthly").strip()
            if kind == "one_time":
                db.execute(
                    "INSERT INTO documents (title, institution, document_type, description, status, due_date, responsible_person) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        form_data.get("title", "").strip(),
                        "",
                        "Genel Evrak",
                        "",
                        "waiting",
                        form_data.get("next_due_date", "").strip(),
                        form_data.get("responsible_person", "").strip(),
                    ),
                )
            else:
                db.execute(
                    "INSERT INTO recurring_documents (title, category, frequency, next_due_date, responsible_person, notes) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        form_data.get("title", "").strip(),
                        "Genel",
                        frequency,
                        form_data.get("next_due_date", "").strip(),
                        form_data.get("responsible_person", "").strip(),
                        "",
                    ),
                )
        elif parsed.path == "/documents/update":
            item_id = form_data.get("id", "").strip()
            target_kind = form_data.get("kind", "one_time").strip()
            frequency = form_data.get("frequency", "monthly").strip()
            source_kind = form_data.get("source_kind", target_kind).strip()
            if item_id.isdigit() and source_kind == "one_time" and target_kind == "one_time":
                db.execute(
                    "UPDATE documents SET title = ?, due_date = ?, responsible_person = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (
                        form_data.get("title", "").strip(),
                        form_data.get("next_due_date", "").strip(),
                        "",
                        int(item_id),
                    ),
                )
            elif item_id.isdigit() and source_kind == "recurring" and target_kind == "recurring":
                db.execute(
                    "UPDATE recurring_documents SET title = ?, frequency = ?, next_due_date = ?, responsible_person = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (
                        form_data.get("title", "").strip(),
                        frequency,
                        form_data.get("next_due_date", "").strip(),
                        "",
                        int(item_id),
                    ),
                )
            elif item_id.isdigit() and source_kind == "one_time" and target_kind == "recurring":
                db.execute("DELETE FROM documents WHERE id = ?", (int(item_id),))
                db.execute(
                    "INSERT INTO recurring_documents (title, category, frequency, next_due_date, responsible_person, notes) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        form_data.get("title", "").strip(),
                        "Genel",
                        frequency,
                        form_data.get("next_due_date", "").strip(),
                        "",
                        "",
                    ),
                )
            elif item_id.isdigit() and source_kind == "recurring" and target_kind == "one_time":
                db.execute("DELETE FROM recurring_documents WHERE id = ?", (int(item_id),))
                db.execute(
                    "INSERT INTO documents (title, institution, document_type, description, status, due_date, responsible_person) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        form_data.get("title", "").strip(),
                        "",
                        "Genel Evrak",
                        "",
                        "waiting",
                        form_data.get("next_due_date", "").strip(),
                        "",
                    ),
                )
        elif parsed.path == "/documents/delete":
            item_id = form_data.get("id", "").strip()
            kind = form_data.get("kind", "").strip()
            if item_id.isdigit() and kind == "one_time":
                db.execute("DELETE FROM documents WHERE id = ?", (int(item_id),))
            elif item_id.isdigit() and kind == "recurring":
                db.execute("DELETE FROM recurring_documents WHERE id = ?", (int(item_id),))
        elif parsed.path == "/documents/toggle":
            item_id = form_data.get("id", "").strip()
            kind = form_data.get("kind", "").strip()
            next_state = form_data.get("next_state", "done").strip()
            if item_id.isdigit() and kind == "one_time":
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
            db.execute(
                "INSERT INTO suppliers (company_name, contact_name, phone, email, service_type, price_notes, notes, next_contact_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    form_data.get("company_name", "").strip(),
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
        elif parsed.path == "/suppliers/update":
            item_id = form_data.get("id", "").strip()
            if item_id.isdigit():
                phone = _normalize_phone(form_data.get("phone", "").strip())
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
        elif parsed.path == "/suppliers/delete":
            item_id = form_data.get("id", "").strip()
            if item_id.isdigit():
                db.execute("DELETE FROM supplier_interactions WHERE supplier_id = ?", (int(item_id),))
                db.execute("DELETE FROM suppliers WHERE id = ?", (int(item_id),))
        elif parsed.path == "/supplier-notes":
            supplier_id = form_data.get("supplier_id", "").strip()
            if supplier_id.isdigit():
                db.execute(
                    "INSERT INTO supplier_interactions (supplier_id, interaction_date, notes) VALUES (?, ?, ?)",
                    (
                        int(supplier_id),
                        form_data.get("interaction_date", "").strip(),
                        form_data.get("notes", "").strip(),
                    ),
                )
        elif parsed.path == "/supplier-notes/update":
            supplier_id = form_data.get("supplier_id", "").strip()
            note_id = form_data.get("note_id", "").strip()
            if supplier_id.isdigit() and note_id.isdigit():
                db.execute(
                    "UPDATE supplier_interactions SET interaction_date = ?, notes = ? WHERE id = ? AND supplier_id = ?",
                    (
                        form_data.get("interaction_date", "").strip(),
                        form_data.get("notes", "").strip(),
                        int(note_id),
                        int(supplier_id),
                    ),
                )
        elif parsed.path == "/supplier-notes/delete":
            supplier_id = form_data.get("supplier_id", "").strip()
            note_id = form_data.get("note_id", "").strip()
            if supplier_id.isdigit() and note_id.isdigit():
                db.execute(
                    "DELETE FROM supplier_interactions WHERE id = ? AND supplier_id = ?",
                    (int(note_id), int(supplier_id)),
                )
        elif parsed.path == "/events":
            event_levels = _normalize_event_levels(parsed_body.get("level", []))
            db.execute(
                "INSERT INTO events (title, event_date, level, notes) VALUES (?, ?, ?, ?)",
                (
                    form_data.get("title", "").strip(),
                    form_data.get("event_date", "").strip(),
                    ",".join(event_levels),
                    "",
                ),
            )
        elif parsed.path == "/events/update":
            item_id = form_data.get("id", "").strip()
            if item_id.isdigit():
                event_levels = _normalize_event_levels(parsed_body.get("level", []))
                db.execute(
                    "UPDATE events SET title = ?, event_date = ?, level = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (
                        form_data.get("title", "").strip(),
                        form_data.get("event_date", "").strip(),
                        ",".join(event_levels),
                        int(item_id),
                    ),
                )
        elif parsed.path == "/events/delete":
            item_id = form_data.get("id", "").strip()
            if item_id.isdigit():
                db.execute("DELETE FROM events WHERE id = ?", (int(item_id),))
        else:
            self.respond(HTTPStatus.NOT_FOUND, not_found_page())
            return

        if parsed.path == "/meetings":
            self.redirect(f"/meetings?meeting={meeting_id}")
        elif parsed.path in {"/tasks/toggle", "/tasks/update", "/tasks/delete"}:
            self.redirect("/tasks")
        elif parsed.path in {"/meetings/update"}:
            self.redirect(f"/meetings?meeting={form_data.get('id', '').strip()}")
        elif parsed.path in {"/meetings/delete"}:
            self.redirect("/meetings")
        elif parsed.path in {"/meeting-templates", "/meeting-templates/delete"}:
            self.redirect("/meetings?tab=settings")
        elif parsed.path in {"/meetings/task"}:
            self.redirect(f"/meetings?meeting={form_data.get('meeting_id', '').strip()}")
        elif parsed.path in {"/documents/update", "/documents/delete", "/documents/toggle"}:
            self.redirect("/documents")
        elif parsed.path in {"/events/update", "/events/delete"}:
            self.redirect("/events")
        elif parsed.path in {"/suppliers/update"}:
            self.redirect(f"/suppliers?supplier={form_data.get('id', '').strip()}")
        elif parsed.path in {"/supplier-notes", "/supplier-notes/update", "/supplier-notes/delete"}:
            self.redirect(f"/suppliers?supplier={form_data.get('supplier_id', '').strip()}")
        else:
            self.redirect(parsed.path)

    def dashboard(self) -> None:
        summary = {
            "pending_tasks": db.fetch_one(
                "SELECT COUNT(*) AS count FROM tasks WHERE status IN ('pending', 'in_progress')"
            )["count"],
            "upcoming_documents": db.fetch_one(
                "SELECT COUNT(*) AS count FROM documents "
                "WHERE due_date IS NOT NULL AND due_date != '' AND due_date <= date('now', '+7 day')"
            )["count"],
            "meeting_count": db.fetch_one("SELECT COUNT(*) AS count FROM meeting_notes")["count"],
            "supplier_count": db.fetch_one("SELECT COUNT(*) AS count FROM suppliers")["count"],
            "event_count": db.fetch_one(
                "SELECT COUNT(*) AS count FROM events WHERE event_date >= date('now', 'localtime')"
            )["count"],
        }
        tasks = db.fetch_all(
            "SELECT * FROM tasks "
            "WHERE status IN ('pending', 'in_progress') "
            "ORDER BY CASE WHEN due_date IS NULL OR due_date = '' THEN 1 ELSE 0 END, due_date ASC, updated_at DESC LIMIT 5"
        )
        documents = db.fetch_all(
            "SELECT * FROM documents "
            "WHERE status != 'submitted' "
            "ORDER BY CASE WHEN due_date IS NULL OR due_date = '' THEN 1 ELSE 0 END, due_date ASC LIMIT 5"
        )
        meetings = db.fetch_all("SELECT * FROM meeting_notes ORDER BY meeting_date DESC LIMIT 5")
        suppliers = db.fetch_all("SELECT * FROM suppliers ORDER BY next_contact_at ASC LIMIT 5")
        events = db.fetch_all("SELECT * FROM events WHERE event_date >= date('now', 'localtime') ORDER BY event_date ASC LIMIT 5")
        alerts = _build_dashboard_alerts()
        self.respond(HTTPStatus.OK, dashboard_page(summary, tasks, documents, meetings, suppliers, events, alerts))

    def search_page(self, query: dict[str, list[str]]) -> None:
        raw_query = query.get("q", [""])[0].strip()
        groups: list[dict] = []
        if raw_query:
            like = f"%{raw_query}%"
            task_rows = db.fetch_all(
                "SELECT id, title, due_date FROM tasks "
                "WHERE title LIKE ? OR description LIKE ? OR responsible_person LIKE ? "
                "ORDER BY updated_at DESC LIMIT 8",
                (like, like, like),
            )
            document_rows = db.fetch_all(
                "SELECT id, title, due_date FROM documents "
                "WHERE title LIKE ? OR description LIKE ? "
                "ORDER BY updated_at DESC LIMIT 8",
                (like, like),
            )
            meeting_rows = db.fetch_all(
                "SELECT id, title, meeting_date, agenda, notes, decisions FROM meeting_notes "
                "WHERE title LIKE ? OR agenda LIKE ? OR notes LIKE ? OR decisions LIKE ? "
                "ORDER BY meeting_date DESC LIMIT 8",
                (like, like, like, like),
            )
            event_rows = db.fetch_all(
                "SELECT id, title, event_date, level FROM events "
                "WHERE title LIKE ? OR notes LIKE ? OR level LIKE ? "
                "ORDER BY event_date ASC LIMIT 8",
                (like, like, like),
            )
            supplier_rows = db.fetch_all(
                "SELECT id, company_name, contact_name, service_type FROM suppliers "
                "WHERE company_name LIKE ? OR contact_name LIKE ? OR service_type LIKE ? "
                "ORDER BY company_name ASC LIMIT 8",
                (like, like, like),
            )
            groups = [
                {
                    "title": "Görevler",
                    "items": [
                        {"href": "/tasks", "title": row["title"], "meta": f"Termin: {row['due_date'] or '-'}"}
                        for row in task_rows
                    ],
                },
                {
                    "title": "Evraklar",
                    "items": [
                        {"href": "/documents", "title": row["title"], "meta": f"Tarih: {row['due_date'] or '-'}"}
                        for row in document_rows
                    ],
                },
                {
                    "title": "Toplantılar",
                    "items": [
                        {"href": f"/meetings?meeting={row['id']}", "title": row["title"], "meta": f"Tarih: {row['meeting_date'] or '-'}"}
                        for row in meeting_rows
                    ],
                },
                {
                    "title": "Etkinlikler",
                    "items": [
                        {"href": "/events", "title": row["title"], "meta": f"{row['event_date'] or '-'} · {row['level'] or '-'}"}
                        for row in event_rows
                    ],
                },
                {
                    "title": "Tedarikçiler",
                    "items": [
                        {"href": f"/suppliers?supplier={row['id']}", "title": row["company_name"], "meta": f"{row['contact_name'] or '-'} · {row['service_type'] or '-'}"}
                        for row in supplier_rows
                    ],
                },
            ]
            groups = [group for group in groups if group["items"]]
        self.respond(HTTPStatus.OK, search_results_page(raw_query, groups))

    def tasks_page(self, query: dict[str, list[str]]) -> None:
        active_filter = query.get("filter", ["all"])[0]
        active_items = db.fetch_all(_build_tasks_query(active_filter))
        completed_items = db.fetch_all(
            "SELECT * FROM tasks WHERE status = 'completed' "
            "ORDER BY CASE WHEN completed_at IS NULL OR completed_at = '' THEN 1 ELSE 0 END, completed_at DESC, updated_at DESC"
        )
        filter_counts = {
            "all": db.fetch_one("SELECT COUNT(*) AS count FROM tasks WHERE status != 'completed'")["count"],
            "today": db.fetch_one(
                "SELECT COUNT(*) AS count FROM tasks WHERE status != 'completed' AND due_date = date('now', 'localtime')"
            )["count"],
            "upcoming": db.fetch_one(
                "SELECT COUNT(*) AS count FROM tasks WHERE status != 'completed' "
                "AND due_date > date('now', 'localtime') AND due_date <= date('now', 'localtime', '+7 day')"
            )["count"],
            "overdue": db.fetch_one(
                "SELECT COUNT(*) AS count FROM tasks WHERE status != 'completed' "
                "AND due_date != '' AND due_date < date('now', 'localtime')"
            )["count"],
            "no_date": db.fetch_one(
                "SELECT COUNT(*) AS count FROM tasks WHERE status != 'completed' "
                "AND (due_date IS NULL OR due_date = '')"
            )["count"],
        }
        edit_item = None
        edit_values = query.get("edit", [])
        if edit_values and edit_values[0].isdigit():
            edit_item = db.fetch_one("SELECT * FROM tasks WHERE id = ?", (int(edit_values[0]),))
        self.respond(HTTPStatus.OK, tasks_page(active_items, completed_items, edit_item, active_filter, filter_counts))

    def meetings_page(self, query: dict[str, list[str]]) -> None:
        active_tab = query.get("tab", ["notes"])[0]
        items = db.fetch_all("SELECT * FROM meeting_notes ORDER BY meeting_date DESC, id DESC")
        templates = db.fetch_all("SELECT * FROM meeting_templates ORDER BY sort_order ASC, title ASC")
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
        edit_item = None
        edit_id = query.get("edit", [""])[0]
        if edit_id.isdigit():
            edit_item = db.fetch_one("SELECT * FROM meeting_notes WHERE id = ?", (int(edit_id),))
        show_new = query.get("new", [""])[0] == "1"
        page = meetings_dashboard_page(items, selected_item, templates, active_tab, edit_item, show_new)
        self.respond(HTTPStatus.OK, page)

    def documents_page(self, query: dict[str, list[str]]) -> None:
        active_filters = [value for value in query.get("filter", []) if value in {"today", "upcoming", "overdue", "recurring"}]
        active_items, completed_items = _build_document_items()
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
        page = documents_dashboard_page_filtered(filtered_items, completed_items, quick_document_form(), edit_item, active_filters, filter_counts)
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
        calendar_source = items or db.fetch_all("SELECT * FROM events ORDER BY event_date ASC, title ASC")
        if month_param:
            try:
                ref_date = datetime.strptime(month_param + "-01", "%Y-%m-%d")
            except ValueError:
                ref_date = datetime.now()
        elif calendar_source:
            first = calendar_source[0]
            try:
                ref_date = datetime.strptime(first["event_date"][:10], "%Y-%m-%d")
            except ValueError:
                ref_date = today
        else:
            ref_date = today
        date_map: dict[str, list[str]] = {}
        for item in items:
            date_map.setdefault(item["event_date"], []).append(item["title"])
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
                calendar_nav_bar(prev_href, next_href),
                edit_item,
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
        page = suppliers_dashboard_page(items, selected_supplier, notes, edit_item, note_edit, show_note_form)
        self.respond(HTTPStatus.OK, page)

    def serve_static(self, request_path: str) -> None:
        file_path = STATIC_DIR / request_path.removeprefix("/static/")
        if not file_path.exists() or not file_path.is_file():
            self.respond(HTTPStatus.NOT_FOUND, b"Not found", content_type="text/plain; charset=utf-8")
            return

        content_type = "text/plain; charset=utf-8"
        if file_path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif file_path.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"

        self.respond(HTTPStatus.OK, file_path.read_bytes(), content_type=content_type)

    def respond(self, status: HTTPStatus, content: bytes, content_type: str = "text/html; charset=utf-8") -> None:
        self.send_response(status.value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER.value)
        self.send_header("Location", location)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:
        return


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    db.init_db()
    server = ThreadingHTTPServer((host, port), MyNotesHandler)
    print(f"My Notes running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _build_tasks_query(active_filter: str) -> str:
    base_query = (
        "SELECT * FROM tasks WHERE status != 'completed' "
    )
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
    return base_query + filter_clauses.get(active_filter, "") + ordering


def _build_dashboard_alerts() -> list[dict]:
    alerts: list[dict] = []

    overdue_tasks = db.fetch_all(
        "SELECT title, due_date FROM tasks "
        "WHERE status IN ('pending', 'in_progress') AND due_date != '' AND due_date < date('now', 'localtime') "
        "ORDER BY due_date ASC LIMIT 3"
    )
    for row in overdue_tasks:
        alerts.append(
            {
                "tone": "danger",
                "title": "Geciken görev",
                "detail": row["title"],
                "meta": row["due_date"] or "-",
            }
        )

    upcoming_docs = db.fetch_all(
        "SELECT title, due_date FROM documents "
        "WHERE status != 'submitted' AND due_date != '' AND due_date <= date('now', 'localtime', '+7 day') "
        "ORDER BY due_date ASC LIMIT 3"
    )
    for row in upcoming_docs:
        alerts.append(
            {
                "tone": "warn",
                "title": "Yaklaşan evrak",
                "detail": row["title"],
                "meta": row["due_date"] or "-",
            }
        )

    today_events = db.fetch_all(
        "SELECT title, event_date FROM events "
        "WHERE event_date = date('now', 'localtime') "
        "ORDER BY event_date ASC, title ASC LIMIT 3"
    )
    for row in today_events:
        alerts.append(
            {
                "tone": "info",
                "title": "Bugünkü etkinlik",
                "detail": row["title"],
                "meta": row["event_date"] or "-",
            }
        )

    return alerts[:6]


def _build_document_items() -> tuple[list[dict], list[dict]]:
    active_items: list[dict] = []
    completed_items: list[dict] = []
    for row in db.fetch_all("SELECT * FROM documents"):
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
                "responsible_person": row["responsible_person"] or "",
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
    for row in db.fetch_all("SELECT * FROM recurring_documents WHERE is_active = 1"):
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
                "responsible_person": row["responsible_person"] or "",
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

