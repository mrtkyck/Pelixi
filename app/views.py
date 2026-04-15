from __future__ import annotations

from datetime import date, datetime
from html import escape
import calendar


NAV_ITEMS = [
    ("/", "Dashboard"),
    ("/tasks", "Görevler"),
    ("/meetings", "Toplantı Notları"),
    ("/documents", "Evrak Takibi"),
    ("/events", "Etkinlik Takvimi"),
    ("/suppliers", "Tedarikçiler"),
]

PRIORITY_LABELS = {
    "low": "Düşük",
    "medium": "Orta",
    "high": "Yüksek",
    "critical": "Kritik",
}

TASK_STATUS_LABELS = {
    "pending": "Bekliyor",
    "in_progress": "Devam Ediyor",
    "completed": "Tamamlandı",
    "cancelled": "İptal Edildi",
}

DOCUMENT_STATUS_LABELS = {
    "preparing": "Hazırlanıyor",
    "waiting": "Beklemede",
    "submitted": "Teslim Edildi",
    "overdue": "Gecikti",
}

FREQUENCY_LABELS = {
    "weekly": "Haftalık",
    "monthly": "Aylık",
    "quarterly": "3 Aylık",
    "semiannual": "6 Aylık",
    "yearly": "Yıllık",
    "custom": "Özel Periyot",
}

TASK_FILTERS = [
    ("all", "Tümü"),
    ("today", "Bugün"),
    ("upcoming", "Yaklaşan"),
    ("overdue", "Geciken"),
    ("no_date", "Tarihsiz"),
]

DOCUMENT_FILTERS = [
    ("all", "Tümü"),
    ("today", "Bugün"),
    ("upcoming", "Yaklaşan"),
    ("overdue", "Geciken"),
    ("recurring", "Tekrarlı"),
]

EVENT_LEVELS = [
    ("all", "Tümü"),
    ("Anasınıfı", "Anasınıfı"),
    ("İlkokul", "İlkokul"),
    ("Ortaokul", "Ortaokul"),
    ("Lise", "Lise"),
]
EVENT_LEVEL_OPTIONS = [(value, label) for value, label in EVENT_LEVELS if value != "all"]

CALENDAR_VIEWS = [
    ("month", "Aylık"),
    ("year", "Yıllık"),
]

MONTH_NAMES = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
WEEKDAY_NAMES = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]


def layout(title: str, body: str, current_path: str) -> bytes:
    nav_links = []
    for path, label in NAV_ITEMS:
        css_class = "nav-link active" if path == current_path else "nav-link"
        nav_links.append(f'<a class="{css_class}" href="{path}">{escape(label)}</a>')
    html = f"""
    <!doctype html>
    <html lang="tr">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>{escape(title)} | My Notes</title>
      <link rel="stylesheet" href="/static/style.css">
    </head>
    <body>
      <div class="app-shell">
        <aside class="sidebar">
          <div class="sidebar-brand"><span class="brand-mark">My</span><span class="brand-name">Notes</span></div>
          <form class="sidebar-search" method="get" action="/search">
            <input type="search" name="q" placeholder="Genel arama" aria-label="Genel arama">
            <button type="submit">Ara</button>
          </form>
          <nav class="sidebar-nav">{''.join(nav_links)}</nav>
          <div class="sidebar-footer-note">Copyright @2026 M.Kayacık v.1</div>
        </aside>
        <main class="main-content">{body}</main>
      </div>
    </body>
    </html>
    """
    return html.encode("utf-8")


def dashboard_page(summary: dict, tasks: list, documents: list, meetings: list, suppliers: list, events: list, alerts: list) -> bytes:
    body = f"""
    <section class="documents-toolbar dashboard-toolbar">
      <div>
        <p class="eyebrow">Genel Bakış</p>
        <h2>Dashboard</h2>
      </div>
      <a class="button secondary dashboard-toolbar-button" href="/tasks">Görevlere Git</a>
    </section>
    <section class="stats-grid dashboard-stats-grid">
      {stat_card("Bekleyen Görev", summary["pending_tasks"], "Bugün odaklanılacak işler")}
      {stat_card("Yaklaşan Evrak", summary["upcoming_documents"], "7 gün içindeki tarihler")}
      {stat_card("Toplantı Notu", summary["meeting_count"], "Kayıtlı son notlar")}
      {stat_card("Etkinlik", summary["event_count"], "Yaklaşan etkinlik kaydı")}
    </section>
    {alert_panel(alerts)}
    <section class="dashboard-columns">
      <div class="dashboard-column">
        {record_panel("Bugünün Görevleri", tasks, render_task_item)}
        {record_panel("Son Toplantı Notları", meetings, render_meeting_item)}
      </div>
      <div class="dashboard-column">
        {record_panel("Yaklaşan Evraklar", documents, render_document_item)}
        {record_panel("Yaklaşan Etkinlikler", events, render_event_card)}
      </div>
    </section>
    """
    return layout("Dashboard", body, "/")


def alert_panel(items: list) -> str:
    rows = "".join(render_alert_item(item) for item in items)
    if not rows:
        rows = '<p class="empty-state">Bugün için kritik bir uyarı görünmüyor.</p>'
    return f'<section class="panel alert-panel"><div class="panel-header"><h3>Uyarılar ve Hatırlatmalar</h3></div><div class="alert-list">{rows}</div></section>'


def render_alert_item(item: dict) -> str:
    tone = escape(item.get("tone", "neutral"))
    meta = escape(item.get("meta", ""))
    return f'<article class="alert-item {tone}"><div class="alert-copy"><h4>{escape(item["title"])}</h4><p>{escape(item["detail"])}</p></div><div class="alert-meta">{meta}</div></article>'


def search_results_page(query: str, groups: list[dict]) -> bytes:
    body = f"""
    <section class="documents-toolbar dashboard-toolbar">
      <div><p class="eyebrow">Genel Arama</p><h2>Arama Sonuçları</h2></div>
      <span class="badge">{escape(query) if query else 'Arama yok'}</span>
    </section>
    <section class="panel search-panel">
      <div class="panel-header"><h3>{escape(query) + ' için sonuçlar' if query else 'Arama yapmak için bir kelime yazın'}</h3></div>
      <div class="search-groups">{''.join(render_search_group(group) for group in groups) if query else '<p class="empty-state">Sidebar aramasından görev, evrak, toplantı, etkinlik veya tedarikçi arayabilirsiniz.</p>'}</div>
    </section>
    """
    return layout("Arama", body, "")


def render_search_group(group: dict) -> str:
    items = group.get("items", [])
    inner = "".join(
        f'<a class="search-result-row" href="{escape(item["href"])}"><strong>{escape(item["title"])}</strong><span>{escape(item["meta"])}</span></a>'
        for item in items
    ) or '<p class="empty-state">Eşleşme yok.</p>'
    return f'<section class="search-group"><div class="panel-header compact-header"><h3>{escape(group["title"])}</h3><span class="badge">{len(items)} sonuç</span></div><div class="search-result-list">{inner}</div></section>'


def module_page(title: str, subtitle: str, form_html: str, list_title: str, items: list, item_renderer, current_path: str) -> bytes:
    body = f'<section class="documents-toolbar dashboard-toolbar"><div><p class="eyebrow">Modül</p><h2>{escape(title)}</h2></div></section><section class="panel"><div class="panel-header"><h3>{escape(list_title)}</h3></div>{render_list(items, item_renderer)}</section>'
    return layout(title, body, current_path)


def stat_card(label: str, value: int, detail: str) -> str:
    return f'<article class="stat-card"><p>{escape(label)}</p><strong>{value}</strong><span>{escape(detail)}</span></article>'


def record_panel(title: str, items: list, item_renderer) -> str:
    return f'<section class="panel"><div class="panel-header"><h3>{escape(title)}</h3></div><div class="record-list">{render_list(items, item_renderer)}</div></section>'


def render_list(items: list, item_renderer) -> str:
    if not items:
        return '<p class="empty-state">Henüz kayıt yok.</p>'
    return "".join(item_renderer(item) for item in items)


def translate_label(value: str, mapping: dict[str, str]) -> str:
    return mapping.get(value, value)


def input_field(name: str, label: str, input_type: str = "text", value: str = "", required: bool = False, placeholder: str = "", extra_attrs: str = "") -> str:
    required_attr = " required" if required else ""
    placeholder_attr = f' placeholder="{escape(placeholder)}"' if placeholder else ""
    extra_attr = f" {extra_attrs}" if extra_attrs else ""
    return f'<label class="field"><span>{escape(label)}</span><input type="{escape(input_type)}" name="{escape(name)}" value="{escape(value)}"{placeholder_attr}{required_attr}{extra_attr}></label>'


def textarea_field(name: str, label: str, value: str = "") -> str:
    return f'<label class="field"><span>{escape(label)}</span><textarea name="{escape(name)}" rows="4">{escape(value)}</textarea></label>'


def select_field(name: str, label: str, options: dict[str, str], selected: str, css_class: str = "") -> str:
    rendered_options = []
    if selected == "":
        rendered_options.append('<option value="" selected></option>')
    for option, option_label in options.items():
        selected_attr = " selected" if option == selected else ""
        rendered_options.append(f'<option value="{escape(option)}"{selected_attr}>{escape(option_label)}</option>')
    class_attr = f' class="{escape(css_class)}"' if css_class else ""
    return f'<label class="field"><span>{escape(label)}</span><select name="{escape(name)}"{class_attr}>{"".join(rendered_options)}</select></label>'


def split_lines(value: str | None) -> list[str]:
    if not value:
        return []
    return [line.strip('- ').strip() for line in value.splitlines() if line.strip()]


def first_nonempty_line(value: str | None) -> str:
    lines = split_lines(value)
    return lines[0] if lines else ""


def format_date(value: str | None) -> str:
    if not value:
        return "-"
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value[:19], fmt).strftime("%d.%m.%Y")
        except ValueError:
            continue
    return value


def format_datetime(value: str | None) -> str:
    if not value:
        return "-"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(value[:19], fmt)
            return parsed.strftime("%d.%m.%Y %H:%M") if fmt.endswith("%S") else parsed.strftime("%d.%m.%Y")
        except ValueError:
            continue
    return value


def row_value(item, key: str, default=""):
    try:
        value = item[key]
    except Exception:
        return default
    return default if value is None else value

def tasks_page(active_items: list, completed_items: list, edit_item=None, active_filter: str = "all", filter_counts: dict | None = None) -> bytes:
    filter_counts = filter_counts or {}
    body = f"""
    <section class="documents-shell">
      <div class="documents-toolbar"><div><p class="eyebrow">Görev</p><h2>Görevler</h2></div><span class="badge">{len(active_items)} aktif</span></div>
      <div class="documents-compact-form quick-task-panel">{quick_task_form_v3()}</div>
      {edit_task_panel_v3(edit_item) if edit_item else ''}
      <div class="documents-table-wrap task-table-panel task-table-panel-active">
        <div class="panel-header"><h3>Aktif Görevler</h3><span class="badge">{len(active_items)} görev</span></div>
        {task_filter_bar(active_filter, filter_counts)}
        {task_table_header_v3(False)}
        <div class="task-table">{render_task_table_v3(active_items, False)}</div>
      </div>
      <div class="documents-table-wrap task-table-panel task-table-panel-completed">
        <div class="panel-header"><h3>Tamamlanan Görevler</h3><span class="badge">{len(completed_items)} görev</span></div>
        {task_table_header_v3(True)}
        <div class="task-table">{render_task_table_v3(completed_items, True)}</div>
      </div>
    </section>
    """
    return layout("Görevler", body, "/tasks")


def task_filter_bar(active_filter: str, filter_counts: dict[str, int]) -> str:
    chips = []
    for value, label in TASK_FILTERS:
        css = "filter-chip active" if value == active_filter else "filter-chip"
        href = "/tasks" if value == "all" else f"/tasks?filter={value}"
        chips.append(f'<a class="{css}" href="{href}"><span>{escape(label)}</span><strong>{filter_counts.get(value, 0)}</strong></a>')
    return f'<div class="filter-bar">{"".join(chips)}</div>'


def quick_task_form_v3() -> str:
    return f"""
    <form method="post" action="/tasks" class="quick-task-form">
      <div class="quick-task-grid quick-task-grid-v2">
        {input_field("title", "Görev", required=True, placeholder="Örnek: Veli toplantısı notlarını hazırla")}
        {input_field("responsible_person", "Sorumlu", placeholder="Şimdilik boş kalabilir")}
        {select_field("priority", "Öncelik", PRIORITY_LABELS, "medium")}
        {input_field("due_date", "Son Tarih", input_type="date", value=str(date.today()))}
        <button class="button" type="submit">Ekle</button>
      </div>
    </form>
    """


def edit_task_panel_v3(item) -> str:
    return f"""
    <div class="panel quick-task-panel">
      <div class="panel-header"><h3>Görevi Düzenle</h3><a class="text-link" href="/tasks">Vazgeç</a></div>
      <form method="post" action="/tasks/update" class="quick-task-form">
        <input type="hidden" name="id" value="{item['id']}">
        <div class="quick-task-grid quick-task-grid-v2">
          {input_field("title", "Görev", required=True, value=item["title"])}
          {input_field("responsible_person", "Sorumlu", value=row_value(item, "responsible_person") or "", placeholder="Boş bırakılabilir")}
          {select_field("priority", "Öncelik", PRIORITY_LABELS, item["priority"])}
          {input_field("due_date", "Son Tarih", input_type="date", value=row_value(item, "due_date") or "")}
          <button class="button" type="submit">Güncelle</button>
        </div>
      </form>
    </div>
    """


def task_table_header_v3(completed: bool) -> str:
    actions = "" if completed else "İşlem"
    return f'<div class="task-header-row task-header-row-v2"><span></span><span>Görev</span><span>Sorumlu</span><span>Öncelik</span><span>Son Tarih</span><span>Tamamlanma</span><span>{actions}</span></div>'


def render_task_table_v3(items: list, completed: bool) -> str:
    if not items:
        return '<p class="empty-state">Henüz tamamlanan görev yok.</p>' if completed else '<p class="empty-state">Aktif görev bulunmuyor.</p>'
    return "".join(render_task_row_v3(item, completed) for item in items)


def render_task_row_v3(item, completed: bool) -> str:
    priority_label = translate_label(item["priority"], PRIORITY_LABELS)
    checked = " checked" if completed else ""
    row_class = "task-row done" if completed else "task-row"
    actions = completed_task_actions(item) if completed else active_task_actions(item)
    return f'<article class="{row_class}"><form class="task-toggle-form" method="post" action="/tasks/toggle"><input type="hidden" name="id" value="{item["id"]}"><input type="hidden" name="next_status" value="{"pending" if completed else "completed"}"><button class="task-check{checked}" type="submit" aria-label="Görev durumunu değiştir"></button></form><div class="task-main task-main-v2"><div class="task-cell task-cell-title"><h4>{escape(item["title"])}</h4></div><div class="task-cell">{escape(row_value(item, "responsible_person", "-"))}</div><div class="task-cell task-cell-priority"><span class="priority-chip {escape(item["priority"])}">{escape(priority_label)}</span></div><div class="task-cell task-cell-date">{escape(format_date(row_value(item, "due_date")))}</div><div class="task-cell task-cell-date">{escape(format_datetime(row_value(item, "completed_at")))}</div><div class="task-cell task-cell-actions">{actions}</div></div></article>'


def active_task_actions(item) -> str:
    return f'<div class="row-actions"><a class="mini-link" href="/tasks?edit={item["id"]}">Düzenle</a><form method="post" action="/tasks/delete" class="inline-form"><input type="hidden" name="id" value="{item["id"]}"><button class="mini-link danger" type="submit">Sil</button></form></div>'


def completed_task_actions(item) -> str:
    return f'<div class="row-actions"><form method="post" action="/tasks/delete" class="inline-form"><input type="hidden" name="id" value="{item["id"]}"><button class="mini-link danger" type="submit">Sil</button></form></div>'


def quick_document_form() -> str:
    kind_options = {"one_time": "Tekrarsız", "recurring": "Tekrarlı"}
    return f"""
    <form method="post" action="/documents" class="quick-task-form compact-inline-form document-inline-form">
      <div class="quick-doc-grid">
        {input_field("title", "Evrak", required=True, placeholder="Örnek: Aylık denetim dosyası")}
        {select_field("kind", "Tür", kind_options, "one_time", css_class="document-kind-select")}
        <div class="document-frequency-wrap is-hidden">{select_field("frequency", "Periyot", FREQUENCY_LABELS, "monthly")}</div>
        {input_field("next_due_date", "Tarih", input_type="date", value=str(date.today()))}
        <button class="button" type="submit">Ekle</button>
      </div>
    </form>
    """


def document_form() -> str:
    return quick_document_form()


def edit_document_panel(item) -> str:
    kind_options = {"one_time": "Tekrarsız", "recurring": "Tekrarlı"}
    frequency_wrap_class = "document-frequency-wrap" + (" is-hidden" if item["kind"] == "one_time" else "")
    return f'<div class="documents-edit-bar"><div class="panel-header"><h3>Evrakı Düzenle</h3><a class="text-link" href="/documents">Vazgeç</a></div><form method="post" action="/documents/update" class="quick-task-form compact-inline-form document-inline-form"><input type="hidden" name="id" value="{item["id"]}"><input type="hidden" name="source_kind" value="{item["kind"]}"><div class="quick-doc-grid">{input_field("title", "Evrak", required=True, value=item["title"])}{select_field("kind", "Tür", kind_options, item["kind"], css_class="document-kind-select")}<div class="{frequency_wrap_class}">{select_field("frequency", "Periyot", FREQUENCY_LABELS, item["frequency"] if item["kind"] == "recurring" else "monthly")}</div>{input_field("next_due_date", "Tarih", input_type="date", value=row_value(item, "date_raw") or "")}<button class="button" type="submit">Güncelle</button></div></form></div>'


def documents_dashboard_page(items: list, quick_form_html: str, edit_item=None) -> bytes:
    return documents_dashboard_page_filtered(items, [], quick_form_html, edit_item, ["all"], {})


def documents_dashboard_page_filtered(active_items: list, completed_items: list, quick_form_html: str, edit_item=None, active_filters: list[str] | None = None, filter_counts: dict | None = None) -> bytes:
    active_filters = active_filters or []
    filter_counts = filter_counts or {}
    body = f"""
    <section class="documents-shell">
      <div class="documents-toolbar"><div><p class="eyebrow">Evrak</p><h2>Evrak Takibi</h2></div><span class="badge">{len(active_items)} aktif</span></div>
      <div class="documents-compact-form">{quick_form_html}</div>
      {edit_document_panel(edit_item) if edit_item else ''}
      <div class="documents-table-wrap task-table-panel task-table-panel-active">{documents_filter_bar(active_filters, filter_counts)}{documents_table_header()}<div class="task-table">{render_documents_table(active_items)}</div></div>
      <div class="documents-table-wrap task-table-panel task-table-panel-completed"><div class="panel-header compact-header"><h3>Tamamlanan Evraklar</h3><span class="badge">{len(completed_items)} kayıt</span></div>{completed_documents_table_header()}<div class="task-table">{render_completed_documents_table(completed_items)}</div></div>
    </section>
    {documents_inline_script()}
    """
    return layout("Evrak Takibi", body, "/documents")


def documents_filter_bar(active_filters: list[str], filter_counts: dict[str, int]) -> str:
    selected = set(item for item in active_filters if item != "all")
    chips = []
    for value, label in DOCUMENT_FILTERS:
        css = "filter-chip active" if ((value == "all" and not selected) or value in selected) else "filter-chip"
        href = _build_document_filter_href(value, active_filters)
        chips.append(f'<a class="{css}" href="{href}"><span>{escape(label)}</span><strong>{filter_counts.get(value, 0)}</strong></a>')
    return f'<div class="filter-bar">{"".join(chips)}</div>'


def _build_document_filter_href(value: str, active_filters: list[str]) -> str:
    current = [item for item in active_filters if item != "all"]
    if value == "all":
        next_filters = []
    elif value in current:
        next_filters = [item for item in current if item != value]
    else:
        next_filters = current + [value]
    return "/documents" if not next_filters else "/documents?" + "&".join(f"filter={item}" for item in next_filters)


def documents_table_header() -> str:
    return '<div class="task-header-row document-header-row"><span></span><span>Evrak</span><span>Periyot</span><span>Tarih</span><span>Son Tamamlanma</span><span>İşlem</span></div>'


def completed_documents_table_header() -> str:
    return '<div class="task-header-row document-header-row"><span></span><span>Evrak</span><span>Periyot</span><span>Son Tarih</span><span>Son Tamamlanma</span><span>İşlem</span></div>'


def render_documents_table(items: list) -> str:
    if not items:
        return '<p class="empty-state">Henüz evrak kaydı yok.</p>'
    return "".join(render_document_row(item) for item in items)


def render_completed_documents_table(items: list) -> str:
    if not items:
        return '<p class="empty-state">Henüz tamamlanan evrak yok.</p>'
    return "".join(render_completed_document_row(item) for item in items)


def render_document_row(item) -> str:
    checked = " checked" if item["is_done"] else ""
    next_state = "undone" if item["is_done"] else "done"
    row_class = "task-row document-row done" if item["is_done"] else "task-row document-row"
    return f'<article class="{row_class}"><form class="task-toggle-form" method="post" action="/documents/toggle"><input type="hidden" name="id" value="{item["id"]}"><input type="hidden" name="kind" value="{item["kind"]}"><input type="hidden" name="next_state" value="{next_state}"><button class="task-check{checked}" type="submit" aria-label="Evrak durumunu değiştir"></button></form><div class="task-main document-main"><div class="task-cell task-cell-title"><h4>{escape(item["title"])}</h4></div><div class="task-cell"><span class="priority-chip medium">{escape(item["frequency_label"])} </span></div><div class="task-cell task-cell-date">{escape(item["date_label"])}</div><div class="task-cell task-cell-date">{escape(item["completed_label"])}</div><div class="task-cell task-cell-actions"><div class="row-actions"><a class="mini-link" href="/documents?edit_kind={item["kind"]}&edit_id={item["id"]}">Düzenle</a><form method="post" action="/documents/delete" class="inline-form"><input type="hidden" name="id" value="{item["id"]}"><input type="hidden" name="kind" value="{item["kind"]}"><button class="mini-link danger" type="submit">Sil</button></form></div></div></div></article>'


def render_completed_document_row(item) -> str:
    return f'<article class="task-row document-row done"><form class="task-toggle-form" method="post" action="/documents/toggle"><input type="hidden" name="id" value="{item["id"]}"><input type="hidden" name="kind" value="{item["kind"]}"><input type="hidden" name="next_state" value="undone"><button class="task-check checked" type="submit" aria-label="Evrak durumunu değiştir"></button></form><div class="task-main completed-document-main"><div class="task-cell task-cell-title"><h4>{escape(item["title"])}</h4></div><div class="task-cell"><span class="priority-chip medium">{escape(item["frequency_label"])} </span></div><div class="task-cell task-cell-date">{escape(item["date_label"])}</div><div class="task-cell task-cell-date">{escape(item["completed_label"])}</div><div class="task-cell task-cell-actions"><div class="row-actions"><form method="post" action="/documents/delete" class="inline-form"><input type="hidden" name="id" value="{item["id"]}"><input type="hidden" name="kind" value="{item["kind"]}"><button class="mini-link danger" type="submit">Sil</button></form></div></div></div></article>'


def documents_inline_script() -> str:
    return """
    <script>
      (() => {
        const syncForm = (form) => {
          const kindSelect = form.querySelector('.document-kind-select');
          const wrap = form.querySelector('.document-frequency-wrap');
          if (!kindSelect || !wrap) return;
          const update = () => {
            const recurring = kindSelect.value === 'recurring';
            wrap.classList.toggle('is-hidden', !recurring);
            const select = wrap.querySelector('select');
            if (select) select.disabled = !recurring;
          };
          kindSelect.addEventListener('change', update);
          update();
        };
        document.querySelectorAll('.document-inline-form').forEach(syncForm);
      })();
    </script>
    """

def quick_event_form() -> str:
    return f"""
    <form method="post" action="/events" class="quick-task-form compact-inline-form event-inline-form">
      <div class="quick-doc-grid event-form-grid">
        {input_field("title", "Etkinlik", required=True, placeholder="Örnek: Bahar Şenliği")}
        {event_level_field([])}
        {input_field("event_date", "Tarih", input_type="date", value=str(date.today()))}
        <button class="button" type="submit">Ekle</button>
      </div>
    </form>
    """


def edit_event_panel(item) -> str:
    return f'<div class="documents-edit-bar"><div class="panel-header"><h3>Etkinliği Düzenle</h3><a class="text-link" href="/events">Vazgeç</a></div><form method="post" action="/events/update" class="quick-task-form compact-inline-form event-inline-form"><input type="hidden" name="id" value="{item["id"]}"><div class="quick-doc-grid event-form-grid">{input_field("title", "Etkinlik", required=True, value=item["title"])}{event_level_field(_split_event_levels(row_value(item, "level")))}{input_field("event_date", "Tarih", input_type="date", value=row_value(item, "event_date") or "")}<button class="button" type="submit">Güncelle</button></div></form></div>'


def events_page(items: list, quick_form_html: str, active_levels: list[str], level_counts: dict[str, int], active_view: str, month_label: str, calendar_html: str, calendar_nav_html: str, edit_item=None) -> bytes:
    body = f'<section class="documents-shell"><div class="documents-toolbar"><div><p class="eyebrow">Etkinlik</p><h2>Etkinlik Takvimi</h2></div><span class="badge">{len(items)} etkinlik</span></div><div class="documents-compact-form">{quick_form_html}</div>{edit_event_panel(edit_item) if edit_item else ""}<div class="events-layout"><div class="documents-table-wrap"><div class="panel-header compact-header"><h3>Kademe Filtreleri</h3></div>{event_filter_bar(active_levels, level_counts, active_view)}{events_table_header()}<div class="task-table">{render_events_table(items)}</div></div><div class="documents-table-wrap calendar-panel"><div class="panel-header compact-header"><h3>{escape(month_label)}</h3></div>{calendar_view_bar(active_view, active_levels)}{calendar_nav_html}{calendar_html}</div></div></section>{event_form_script()}'
    return layout("Etkinlik Takvimi", body, "/events")


def event_filter_bar(active_levels: list[str], level_counts: dict[str, int], active_view: str) -> str:
    selected = set(active_levels)
    links = []
    for value, label in EVENT_LEVELS:
        css = "filter-chip active" if ((value == "all" and not selected) or value in selected) else "filter-chip"
        href = _build_event_filter_href(value, active_levels, active_view)
        links.append(f'<a class="{css}" href="{href}"><span>{escape(label)}</span><strong>{level_counts.get(value, 0)}</strong></a>')
    return f'<div class="filter-bar">{"".join(links)}</div>'


def _build_event_filter_href(value: str, active_levels: list[str], active_view: str) -> str:
    current = [item for item in active_levels if item != "all"]
    if value == "all":
        next_levels = []
    elif value in current:
        next_levels = [item for item in current if item != value]
    else:
        next_levels = current + [value]
    params = []
    if active_view != "month":
        params.append(f"view={active_view}")
    params.extend(f"level={level}" for level in next_levels)
    return "/events" if not params else "/events?" + "&".join(params)


def calendar_view_bar(active_view: str, active_levels: list[str]) -> str:
    links = []
    for value, label in CALENDAR_VIEWS:
        css = "filter-chip active" if value == active_view else "filter-chip"
        params = []
        if value != "month":
            params.append(f"view={value}")
        params.extend(f"level={level}" for level in active_levels)
        href = "/events" if not params else "/events?" + "&".join(params)
        links.append(f'<a class="{css}" href="{href}"><span>{escape(label)}</span></a>')
    return f'<div class="filter-bar calendar-view-bar">{"".join(links)}</div>'


def calendar_nav_bar(prev_href: str, next_href: str) -> str:
    return f'<div class="calendar-nav"><a class="mini-link" href="{escape(prev_href)}">Önceki</a><a class="mini-link" href="{escape(next_href)}">Sonraki</a></div>'


def render_event_calendar(year: int, month: int, date_map: dict[str, list[str]]) -> tuple[str, str]:
    label = f"{MONTH_NAMES[month - 1]} {year}"
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdayscalendar(year, month)
    cells = []
    for week in weeks:
        for day in week:
            if day == 0:
                cells.append('<div class="calendar-cell muted"></div>')
                continue
            key = f"{year:04d}-{month:02d}-{day:02d}"
            events = date_map.get(key, [])
            dots = "".join('<span class="calendar-dot"></span>' for _ in events[:3])
            meta = f'<div class="calendar-meta">{len(events)} etkinlik</div>' if events else ""
            title_attr = f' title="{escape(" | ".join(events))}"' if events else ""
            cells.append(f'<div class="calendar-cell"{title_attr}><strong>{day}</strong><div class="calendar-dots">{dots}</div>{meta}</div>')
    html = '<div class="calendar-grid calendar-weekdays">' + "".join(f'<span>{name}</span>' for name in WEEKDAY_NAMES) + '</div><div class="calendar-grid">' + "".join(cells) + '</div>'
    return label, html


def render_event_year_calendar(year: int, date_map: dict[str, list[str]], active_levels: list[str]) -> tuple[str, str]:
    cards = []
    level_suffix = "".join(f"&level={level}" for level in active_levels)
    for month in range(1, 13):
        count = sum(len(titles) for key, titles in date_map.items() if key.startswith(f"{year:04d}-{month:02d}-"))
        href = f"/events?month={year:04d}-{month:02d}{level_suffix}"
        cards.append(f'<a class="year-calendar-card" href="{href}"><strong>{MONTH_NAMES[month - 1]}</strong><span>{count} etkinlik</span></a>')
    return str(year), '<div class="year-calendar-grid">' + "".join(cards) + '</div>'


def events_table_header() -> str:
    return '<div class="task-header-row event-header-row"><span>Etkinlik</span><span>Kademe</span><span>Tarih</span><span>İşlem</span></div>'


def render_events_table(items: list) -> str:
    if not items:
        return '<p class="empty-state">Henüz etkinlik kaydı yok.</p>'
    return "".join(render_event_row(item) for item in items)


def render_event_row(item) -> str:
    return f'<article class="task-row document-row event-row"><div class="task-main event-main"><div class="task-cell task-cell-title"><h4>{escape(item["title"])}</h4></div><div class="task-cell">{render_event_level_badges(row_value(item, "level", ""))}</div><div class="task-cell task-cell-date">{escape(format_date(row_value(item, "event_date")))}</div><div class="task-cell task-cell-actions"><div class="row-actions"><a class="mini-link" href="/events?edit={item["id"]}">Düzenle</a><form method="post" action="/events/delete" class="inline-form"><input type="hidden" name="id" value="{item["id"]}"><button class="mini-link danger" type="submit">Sil</button></form></div></div></div></article>'


def event_level_field(selected_levels: list[str]) -> str:
    selected_set = set(selected_levels)
    summary = ", ".join(selected_levels) if selected_levels else "Kademe seçin"
    chips = []
    for value, label in EVENT_LEVEL_OPTIONS:
        checked = " checked" if value in selected_set else ""
        active = " event-level-chip active" if value in selected_set else " event-level-chip"
        chips.append(f'<label class="{active}"><input type="checkbox" name="level" value="{escape(value)}"{checked}><span>{escape(label)}</span></label>')
    return f'<div class="field event-level-field"><span>Kademe</span><details class="event-level-dropdown" data-event-level-dropdown><summary class="event-level-summary" data-event-level-summary>{escape(summary)}</summary><div class="event-level-group">{"".join(chips)}</div></details></div>'


def render_event_level_badges(raw_levels: str) -> str:
    levels = _split_event_levels(raw_levels)
    if not levels:
        return '<span class="priority-chip medium">Belirtilmedi</span>'
    return "".join(f'<span class="priority-chip medium">{escape(level)}</span>' for level in levels)


def format_event_levels(raw_levels: str | None) -> str:
    levels = _split_event_levels(raw_levels)
    return ", ".join(levels) if levels else "Belirtilmedi"


def _split_event_levels(raw_levels: str | None) -> list[str]:
    if not raw_levels:
        return []
    return [part.strip() for part in raw_levels.split(",") if part.strip()]


def event_form_script() -> str:
    return """
    <script>
      (() => {
        const updateDropdown = (details) => {
          const summary = details.querySelector('[data-event-level-summary]');
          const checked = [...details.querySelectorAll('input[type="checkbox"]:checked')].map((node) => node.value);
          if (summary) summary.textContent = checked.length ? checked.join(', ') : 'Kademe seçin';
        };
        document.querySelectorAll('[data-event-level-dropdown]').forEach((details) => {
          updateDropdown(details);
          details.addEventListener('change', () => updateDropdown(details));
        });
      })();
    </script>
    """

def quick_supplier_form_v2() -> str:
    return f"""
    <form method="post" action="/suppliers" class="quick-task-form compact-inline-form">
      <div class="quick-supplier-grid">
        {input_field("company_name", "Firma", required=True, placeholder="Örnek: Mavi Matbaa")}
        {input_field("contact_name", "Yetkili", placeholder="Örnek: Ayşe Demir")}
        {input_field("phone", "Telefon", placeholder="Örnek: 5551234567", extra_attrs='inputmode="numeric" maxlength="10" pattern="[0-9]{10}" oninput="this.value=this.value.replace(/\\D/g, \"\").slice(0,10)"')}
        {input_field("service_type", "Hizmet", placeholder="Örnek: Baskı / Servis / Yemek")}
        <button class="button" type="submit">Ekle</button>
      </div>
    </form>
    """


def suppliers_page(items: list, selected_supplier, notes: list, edit_item=None, note_edit=None, show_note_form: bool = False) -> bytes:
    selected_name = selected_supplier["company_name"] if selected_supplier else "Tedarikçi seçin"
    body = f'<section class="documents-shell"><div class="documents-toolbar"><div><p class="eyebrow">Tedarikçi</p><h2>Tedarikçiler</h2></div><span class="badge">{len(items)} kayıt</span></div><div class="documents-compact-form">{quick_supplier_form_v2()}</div>{edit_supplier_panel(edit_item) if edit_item else ""}<div class="documents-table-wrap task-table-panel task-table-panel-completed"><div class="panel-header compact-header"><h3>Tedarikçi Listesi</h3></div>{suppliers_table_header()}<div class="task-table">{render_suppliers_table(items, selected_supplier["id"] if selected_supplier else None)}</div></div><div class="documents-table-wrap supplier-notes-panel"><div class="panel-header compact-header"><h3>{escape(selected_name)} Görüşme Notları</h3></div>{supplier_note_form(selected_supplier, note_edit) if (show_note_form or note_edit) else ""}<div class="supplier-note-list">{render_supplier_notes(notes, selected_supplier)}</div></div></section>'
    return layout("Tedarikçiler", body, "/suppliers")


def edit_supplier_panel(item) -> str:
    return f'<div class="documents-edit-bar"><div class="panel-header"><h3>Tedarikçiyi Düzenle</h3><a class="text-link" href="/suppliers?supplier={item["id"]}">Vazgeç</a></div><form method="post" action="/suppliers/update" class="quick-task-form compact-inline-form"><input type="hidden" name="id" value="{item["id"]}"><div class="quick-supplier-grid">{input_field("company_name", "Firma", required=True, value=item["company_name"])}{input_field("contact_name", "Yetkili", value=row_value(item, "contact_name") or "")}{input_field("phone", "Telefon", value=row_value(item, "phone") or "", extra_attrs='inputmode="numeric" maxlength="10" pattern="[0-9]{10}" oninput="this.value=this.value.replace(/\\D/g, \"\").slice(0,10)"')}{input_field("service_type", "Hizmet", value=row_value(item, "service_type") or "")}<button class="button" type="submit">Güncelle</button></div></form></div>'


def supplier_note_form(selected_supplier, note_edit=None) -> str:
    if not selected_supplier:
        return '<p class="empty-state">Önce listeden bir tedarikçi seçin.</p>'
    action = "/supplier-notes/update" if note_edit else "/supplier-notes"
    button_label = "Güncelle" if note_edit else "Not Ekle"
    cancel_link = f'<a class="text-link" href="/suppliers?supplier={selected_supplier["id"]}">Vazgeç</a>' if note_edit else ""
    note_id_field = f'<input type="hidden" name="note_id" value="{note_edit["id"]}">' if note_edit else ""
    note_date = note_edit["interaction_date"] if note_edit else str(date.today())
    note_text = note_edit["notes"] if note_edit else ""
    return f'<div class="supplier-note-form-wrap"><div class="supplier-note-top"><div><p class="eyebrow">Görüşme</p><h3>{"Görüşme Notunu Düzenle" if note_edit else "Yeni Görüşme Notu"}</h3></div>{cancel_link}</div><form method="post" action="{action}" class="supplier-note-form"><input type="hidden" name="supplier_id" value="{selected_supplier["id"]}">{note_id_field}<div class="quick-note-grid">{input_field("interaction_date", "Görüşme Tarihi", input_type="date", value=note_date)}</div>{textarea_field("notes", "Not", note_text)}<div class="supplier-note-actions"><button class="button" type="submit">{button_label}</button></div></form></div>'


def suppliers_table_header() -> str:
    return '<div class="task-header-row supplier-header-row"><span>Firma</span><span>Yetkili</span><span>Telefon</span><span>Hizmet</span><span>İşlem</span></div>'


def render_suppliers_table(items: list, selected_id: int | None) -> str:
    if not items:
        return '<p class="empty-state">Henüz tedarikçi kaydı yok.</p>'
    return "".join(render_supplier_row(item, selected_id) for item in items)


def render_supplier_row(item, selected_id: int | None) -> str:
    row_class = "task-row supplier-row" + (" selected" if selected_id == item["id"] else "")
    return f'<article class="{row_class}"><div class="task-main supplier-main"><div class="task-cell task-cell-title"><h4><a class="supplier-link" href="/suppliers?supplier={item["id"]}">{escape(item["company_name"])}</a></h4></div><div class="task-cell">{escape(row_value(item, "contact_name", "-"))}</div><div class="task-cell task-cell-date">{escape(row_value(item, "phone", "-"))}</div><div class="task-cell"><span class="supplier-service" title="{escape(row_value(item, "service_type", "-"))}">{escape(row_value(item, "service_type", "-"))}</span></div><div class="task-cell task-cell-actions"><div class="row-actions"><a class="mini-link" href="/suppliers?supplier={item["id"]}&add_note=1">+</a><a class="mini-link" href="/suppliers?supplier={item["id"]}&edit={item["id"]}">Düzenle</a><form method="post" action="/suppliers/delete" class="inline-form"><input type="hidden" name="id" value="{item["id"]}"><button class="mini-link danger" type="submit">Sil</button></form></div></div></div></article>'


def render_supplier_notes(notes: list, selected_supplier) -> str:
    if not selected_supplier:
        return '<p class="empty-state">Görüşme notlarını görmek için bir tedarikçi seçin.</p>'
    if not notes:
        return '<p class="empty-state">Bu tedarikçi için henüz görüşme notu yok.</p>'
    return supplier_notes_table_header() + "".join(render_supplier_note_row(note, selected_supplier["id"]) for note in notes)


def supplier_notes_table_header() -> str:
    return '<div class="task-header-row supplier-note-header-row"><span>Tarih</span><span>Görüşme Notu</span><span>İşlem</span></div>'


def render_supplier_note_row(item, supplier_id: int) -> str:
    return f'<article class="task-row supplier-note-row"><div class="task-main supplier-note-main"><div class="task-cell task-cell-date"><span class="supplier-note-date">{escape(format_date(item["interaction_date"]))}</span></div><div class="task-cell supplier-note-text">{escape(row_value(item, "notes") or "Not girilmemiş.")}</div><div class="task-cell task-cell-actions"><div class="row-actions"><a class="mini-link" href="/suppliers?supplier={supplier_id}&note_edit={item["id"]}">Düzenle</a><form method="post" action="/supplier-notes/delete" class="inline-form"><input type="hidden" name="supplier_id" value="{supplier_id}"><input type="hidden" name="note_id" value="{item["id"]}"><button class="mini-link danger" type="submit">Sil</button></form></div></div></div></article>'


def meetings_workspace_page_v3(items: list, selected_item=None, templates: list | None = None, active_tab: str = "notes", edit_item=None, show_new: bool = False) -> bytes:
    templates = templates or []
    if active_tab == "settings":
        content = meeting_settings_panel_v3(templates)
    elif show_new:
        content = f'<div class="meeting-toolbar-actions meeting-toolbar-actions-start"><a class="mini-link" href="/meetings">Listeye Dön</a></div><div class="documents-compact-form meeting-form-panel"><div class="panel-header compact-header"><h3>Yeni Toplantı</h3></div><form method="post" action="/meetings" class="quick-task-form compact-inline-form meeting-editor" data-meeting-editor>{meeting_quick_form_v3(templates)}</form></div>'
    elif edit_item:
        content = f'<div class="meeting-toolbar-actions meeting-toolbar-actions-start"><a class="mini-link" href="/meetings?meeting={edit_item["id"]}">Detaya Dön</a><a class="mini-link" href="/meetings">Listeye Dön</a></div>{edit_meeting_panel_v3(edit_item, templates)}'
    elif selected_item:
        content = f'<div class="meeting-toolbar-actions meeting-toolbar-actions-start"><a class="mini-link" href="/meetings">Listeye Dön</a><a class="mini-link" href="/meetings?meeting={selected_item["id"]}&edit={selected_item["id"]}">Düzenle</a><form method="post" action="/meetings/delete" class="inline-form"><input type="hidden" name="id" value="{selected_item["id"]}"><button class="mini-link danger" type="submit">Sil</button></form></div><div class="documents-table-wrap task-table-panel task-table-panel-completed"><div class="panel-header compact-header"><h3>{escape(selected_item["title"])}</h3><span class="badge">{escape(format_date(selected_item["meeting_date"]))}</span></div>{render_meeting_detail_v3(selected_item)}</div>'
    else:
        content = f'<div class="meeting-toolbar-actions meeting-toolbar-actions-end"><a class="button" href="/meetings?new=1">Yeni Toplantı</a></div><div class="documents-table-wrap task-table-panel task-table-panel-active"><div class="panel-header compact-header"><h3>Toplantı Listesi</h3><span class="badge">{len(items)} kayıt</span></div>{meetings_table_header_v3()}<div class="task-table">{render_meetings_table_v3(items, None)}</div></div>'
    body = f'<section class="documents-shell meetings-shell"><div class="documents-toolbar"><div><p class="eyebrow">Toplantı</p><h2>Toplantı Notları</h2></div><span class="badge">{len(items)} kayıt</span></div><div class="meeting-tab-bar"><a class="filter-chip {"active" if active_tab == "notes" else ""}" href="/meetings"><span>Toplantılar</span></a><a class="filter-chip {"active" if active_tab == "settings" else ""}" href="/meetings?tab=settings"><span>Başlık Ayarları</span></a></div>{content}</section>{meeting_form_script_v3()}'
    return layout("Toplantı Notları", body, "/meetings")


def meeting_settings_panel_v3(templates: list) -> str:
    rows = []
    for item in templates:
        rows.append(f'<article class="task-row meeting-template-row"><div class="task-main meeting-template-main"><div class="task-cell task-cell-title"><h4>{escape(item["title"])}</h4></div><div class="task-cell task-cell-actions"><div class="row-actions"><form method="post" action="/meeting-templates/delete" class="inline-form"><input type="hidden" name="id" value="{item["id"]}"><button class="mini-link danger" type="submit">Sil</button></form></div></div></div></article>')
    inner = "".join(rows) if rows else '<p class="empty-state">Henüz başlık eklenmemiş.</p>'
    return f'<div class="documents-table-wrap"><div class="panel-header compact-header"><h3>Başlık Seçenekleri</h3></div><form method="post" action="/meeting-templates" class="quick-task-form compact-inline-form"><div class="meeting-template-grid">{input_field("title", "Yeni Başlık", required=True, placeholder="Örnek: Zümre toplantısı")}<button class="button" type="submit">Ekle</button></div></form><div class="task-table meeting-template-list">{inner}</div></div>'


def meeting_quick_form_v3(templates: list) -> str:
    return f'{meeting_title_field_v3(templates)}<div class="meeting-form-grid-tail">{input_field("meeting_date", "Tarih", input_type="date", value=str(date.today()), required=True)}<button class="button" type="submit">Kaydet</button></div>{meeting_line_editor_v3("Gündem", "agenda_item", ["Madde 1", "Madde 2"])}{meeting_line_editor_v3("Kararlar", "decision_item", ["Karar 1"])}{textarea_field("notes", "Notlar")}'


def edit_meeting_panel_v3(item, templates: list) -> str:
    agenda_items = split_lines(row_value(item, "agenda")) or [""]
    decision_items = split_lines(row_value(item, "decisions")) or [""]
    return f'<div class="documents-edit-bar meeting-form-panel"><div class="panel-header compact-header"><h3>Toplantıyı Düzenle</h3><a class="text-link" href="/meetings?meeting={item["id"]}">Kapat</a></div><form method="post" action="/meetings/update" class="quick-task-form compact-inline-form meeting-editor" data-meeting-editor><input type="hidden" name="id" value="{item["id"]}">{meeting_title_field_v3(templates, item["title"])}<div class="meeting-form-grid-tail">{input_field("meeting_date", "Tarih", input_type="date", value=item["meeting_date"], required=True)}<button class="button" type="submit">Güncelle</button></div>{meeting_line_editor_v3("Gündem", "agenda_item", agenda_items)}{meeting_line_editor_v3("Kararlar", "decision_item", decision_items)}{textarea_field("notes", "Notlar", row_value(item, "notes") or "")}</form></div>'


def meeting_title_field_v3(templates: list, selected_title: str = "") -> str:
    options = {str(item["title"]): str(item["title"]) for item in templates}
    options["__custom__"] = "Diğer"
    selected_value = selected_title if selected_title in options else ""
    custom_value = "" if selected_title in options else selected_title
    custom_visible = " is-visible" if custom_value else ""
    return f'<div class="meeting-title-group">{select_field("title", "Başlık", options, selected_value, css_class="meeting-title-select")}<div class="meeting-custom-title{custom_visible}">{input_field("custom_title", "Yeni Başlık", value=custom_value, placeholder="Örnek: Veli temsilcileri toplantısı")}</div></div>'


def meeting_line_editor_v3(label: str, name: str, values: list[str]) -> str:
    rows = "".join(meeting_line_row_v3(name, index, value) for index, value in enumerate(values or [""], start=1))
    singular = "Karar Satırı" if label == "Kararlar" else "Gündem Satırı"
    return f'<div class="meeting-lines-editor" data-line-editor><div class="panel-header compact-header"><h3>{escape(label)}</h3></div><div class="meeting-lines-header"><span>No</span><span>{singular}</span><span>İşlem</span></div><div class="meeting-lines-table" data-line-list data-name="{escape(name)}">{rows}</div><div class="meeting-lines-footer"><button class="mini-link" type="button" data-add-line>Satır Ekle</button></div></div>'


def meeting_line_row_v3(name: str, index: int, value: str) -> str:
    default_placeholders = {"Madde 1", "Madde 2", "Karar 1"}
    input_value = "" if value in default_placeholders else value
    placeholder = value if value in default_placeholders else ""
    placeholder_attr = f' placeholder="{escape(placeholder)}"' if placeholder else ""
    return f'<div class="meeting-line-row" data-line-row><span class="meeting-line-number" data-line-number>{index}.</span><input type="text" name="{escape(name)}" value="{escape(input_value)}"{placeholder_attr}><button class="mini-link danger" type="button" data-remove-line>Sil</button></div>'


def meetings_table_header_v3() -> str:
    return '<div class="task-header-row meeting-header-row"><span>Başlık</span><span>Tarih</span><span>Gündem</span><span>İşlem</span></div>'


def render_meetings_table_v3(items: list, selected_id: int | None) -> str:
    if not items:
        return '<p class="empty-state">Henüz toplantı kaydı yok.</p>'
    return "".join(render_meeting_row_v3(item, selected_id) for item in items)


def render_meeting_row_v3(item, selected_id: int | None) -> str:
    row_class = "task-row meeting-row" + (" selected" if selected_id == item["id"] else "")
    preview = first_nonempty_line(row_value(item, "agenda")) or "-"
    return f'<article class="{row_class}"><div class="task-main meeting-main"><div class="task-cell task-cell-title"><h4><a class="supplier-link" href="/meetings?meeting={item["id"]}">{escape(item["title"])}</a></h4></div><div class="task-cell task-cell-date">{escape(format_date(row_value(item, "meeting_date")))}</div><div class="task-cell meeting-preview">{escape(preview)}</div><div class="task-cell task-cell-actions"><div class="row-actions"><a class="mini-link" href="/meetings?meeting={item["id"]}&edit={item["id"]}">Düzenle</a><form method="post" action="/meetings/delete" class="inline-form"><input type="hidden" name="id" value="{item["id"]}"><button class="mini-link danger" type="submit">Sil</button></form></div></div></div></article>'


def render_meeting_detail_v3(item) -> str:
    if not item:
        return '<p class="empty-state">Detayı görmek için listeden bir toplantı seçin.</p>'
    return f'<div class="meeting-detail-grid">{meeting_detail_section("Gündem", render_numbered_list_v2(row_value(item, "agenda")))}{meeting_detail_section("Kararlar", render_decision_list_v3(item))}{meeting_detail_section("Notlar", render_notes_text_v2(row_value(item, "notes")))}</div>'


def meeting_detail_section(title: str, content: str) -> str:
    return f'<section class="meeting-section"><div class="panel-header compact-header"><h3>{escape(title)}</h3></div>{content}</section>'


def render_numbered_list_v2(value: str | None) -> str:
    lines = split_lines(value)
    if not lines:
        return '<p class="empty-state">Henüz içerik yok.</p>'
    rows = "".join(f'<div class="meeting-detail-row"><span class="meeting-detail-index">{index}.</span><span class="meeting-detail-text">{escape(line)}</span></div>' for index, line in enumerate(lines, start=1))
    return '<div class="meeting-detail-table"><div class="meeting-detail-head"><span>No</span><span>Madde</span></div>' + rows + '</div>'


def render_notes_text_v2(value: str | None) -> str:
    lines = split_lines(value)
    if not lines:
        return '<p class="empty-state">Henüz not girilmemiş.</p>'
    rows = "".join(f'<div class="meeting-detail-row"><span class="meeting-detail-index">{index}.</span><span class="meeting-detail-text">{escape(line)}</span></div>' for index, line in enumerate(lines, start=1))
    return '<div class="meeting-detail-table"><div class="meeting-detail-head"><span>No</span><span>Not</span></div>' + rows + '</div>'


def render_decision_list_v3(item) -> str:
    lines = split_lines(row_value(item, "decisions"))
    if not lines:
        return '<p class="empty-state">Henüz karar girilmemiş.</p>'
    linked_titles = set(item.get("_linked_task_titles", set())) if isinstance(item, dict) else set()
    rows = []
    for index, line in enumerate(lines, start=1):
        if line in linked_titles:
            action_html = '<span class="status-chip success">Eklendi</span>'
        else:
            action_html = f'<form method="post" action="/meetings/task" class="inline-form"><input type="hidden" name="meeting_id" value="{item["id"]}"><input type="hidden" name="decision_text" value="{escape(line)}"><button class="mini-link decision-add-link" type="submit">Göreve Ekle</button></form>'
        rows.append(f'<div class="meeting-detail-row meeting-detail-row-action"><span class="meeting-detail-index">{index}.</span><span class="meeting-detail-text">{escape(line)}</span>{action_html}</div>')
    return '<div class="meeting-detail-table"><div class="meeting-detail-head meeting-detail-head-action"><span>No</span><span>Karar</span><span>İşlem</span></div>' + "".join(rows) + '</div>'


def meeting_form_script_v3() -> str:
    template = meeting_line_row_v3("__NAME__", 1, "").replace("\n", "")
    return f"""
    <script>
      (() => {{
        const template = `{template}`;
        const syncRows = (list) => {{
          [...list.querySelectorAll('[data-line-row]')].forEach((row, index) => {{
            const num = row.querySelector('[data-line-number]');
            if (num) num.textContent = `${{index + 1}}.`;
          }});
        }};
        document.querySelectorAll('[data-line-editor]').forEach((editor) => {{
          const list = editor.querySelector('[data-line-list]');
          const addButton = editor.querySelector('[data-add-line]');
          if (!list || !addButton) return;
          addButton.addEventListener('click', () => {{
            list.insertAdjacentHTML('beforeend', template.replace(/__NAME__/g, list.dataset.name || 'line_item'));
            syncRows(list);
          }});
          list.addEventListener('click', (event) => {{
            const button = event.target.closest('[data-remove-line]');
            if (!button) return;
            const row = button.closest('[data-line-row]');
            if (!row) return;
            row.remove();
            if (!list.querySelector('[data-line-row]')) {{
              list.insertAdjacentHTML('beforeend', template.replace(/__NAME__/g, list.dataset.name || 'line_item'));
            }}
            syncRows(list);
          }});
          syncRows(list);
        }});
        document.querySelectorAll('.meeting-title-select').forEach((select) => {{
          const wrap = select.closest('.meeting-title-group');
          if (!wrap) return;
          const custom = wrap.querySelector('.meeting-custom-title');
          const update = () => custom?.classList.toggle('is-visible', select.value === '__custom__');
          select.addEventListener('change', update);
          update();
        }});
      }})();
    </script>
    """


def render_task_item(item) -> str:
    status_label = translate_label(item["status"], TASK_STATUS_LABELS)
    priority_label = translate_label(item["priority"], PRIORITY_LABELS)
    return f'<article class="record-card"><div class="record-top"><h4>{escape(item["title"])}</h4><span class="status-pill {escape(item["status"])}">{escape(status_label)}</span></div><p>{escape(row_value(item, "description") or "Açıklama eklenmemiş.")}</p><div class="meta-row"><span>{escape(row_value(item, "category", "Genel"))}</span><span>Öncelik: {escape(priority_label)}</span><span>Termin: {escape(row_value(item, "due_date", "-"))}</span></div></article>'


def render_document_item(item) -> str:
    status_label = translate_label(item["status"], DOCUMENT_STATUS_LABELS)
    return f'<article class="record-card"><div class="record-top"><h4>{escape(item["title"])}</h4><span class="status-pill {escape(item["status"])}">{escape(status_label)}</span></div><p>{escape(row_value(item, "description") or "Açıklama eklenmemiş.")}</p><div class="meta-row"><span>{escape(row_value(item, "institution", "Kurum belirtilmedi"))}</span><span>Termin: {escape(row_value(item, "due_date", "-"))}</span></div></article>'


def render_supplier_item(item) -> str:
    return f'<article class="record-card"><div class="record-top"><h4>{escape(item["company_name"])}</h4><span class="status-pill neutral">{escape(row_value(item, "service_type") or "Tedarikçi")}</span></div><p>{escape(row_value(item, "notes") or "Not eklenmemiş.")}</p><div class="meta-row"><span>{escape(row_value(item, "contact_name", "Yetkili belirtilmedi"))}</span><span>{escape(row_value(item, "phone", "-"))}</span></div></article>'


def render_meeting_item(item) -> str:
    return f'<article class="record-card"><div class="record-top"><h4>{escape(item["title"])}</h4><span class="status-pill neutral">{escape(format_date(row_value(item, "meeting_date")))}</span></div><p>{escape(row_value(item, "agenda") or "Gündem yazılmamış.")}</p><div class="meta-row"><span>{escape(row_value(item, "meeting_type", "Genel"))}</span><span>{escape(row_value(item, "participants") or "Katılımcı belirtilmedi")}</span></div></article>'


def render_event_card(item) -> str:
    return f'<article class="record-card"><div class="record-top"><h4>{escape(item["title"])}</h4><span class="status-pill neutral">{escape(format_date(row_value(item, "event_date")))}</span></div><p>{escape(row_value(item, "notes") or "Not eklenmemiş.")}</p><div class="meta-row"><span>{escape(format_event_levels(row_value(item, "level")))}</span></div></article>'


def not_found_page() -> bytes:
    body = '<section class="documents-toolbar dashboard-toolbar"><div><p class="eyebrow">404</p><h2>Sayfa bulunamadı</h2><p>İstediğiniz adres mevcut değil. Sol menüden ana modüllere dönebilirsiniz.</p></div><a class="button" href="/">Dashboard\'a dön</a></section>'
    return layout("Sayfa Bulunamadı", body, "")
