from __future__ import annotations

from datetime import date, datetime, timedelta
from html import escape
import calendar
import json
from urllib.parse import urlencode

from app.firm_service import get_active_user_firm_name, get_user_sidebar_meta


MAIN_NAV_ITEMS = [
    ("/", "Dashboard"),
    ("/notifications", "Bildirimler"),
    ("/tasks", "Görevler"),
    ("/meetings", "Toplantılar"),
    ("/documents", "Evraklar"),
    ("/events", "Takvim"),
    ("/suppliers", "Tedarikçiler"),
]

SETTINGS_NAV_ITEMS = [
    ("/notification-settings", "Bildirim Ayarları"),
    ("/backup-settings", "Yedekleme"),
    ("/file-settings", "Dosya Ayarları"),
    ("/audit-logs", "Kayıt Geçmişi"),
    ("/companies", "Firmalar"),
    ("/branches", "Şubeler"),
    ("/roles", "Roller"),
    ("/users", "Kullanıcılar"),
    ("/permissions", "Yetkiler"),
    ("/meeting-templates", "Başlık Ayarları"),
]

NAV_ICONS = {
    "/": (
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 10.5 12 4l8 6.5"/><path d="M6.5 9.5V20h11V9.5"/><path d="M10 20v-5h4v5"/></svg>'
    ),
    "/tasks": (
        '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="6" width="14" height="14" rx="3"/><path d="m9 12 2 2 4-5"/></svg>'
    ),
    "/notifications": (
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.5 10a5.5 5.5 0 0 1 11 0c0 4 1.5 5 1.5 5h-14s1.5-1 1.5-5Z"/><path d="M9.8 18a2.3 2.3 0 0 0 4.4 0"/></svg>'
    ),
    "/meetings": (
        '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5" width="16" height="12" rx="3"/><path d="M8 10h8M8 13h5"/><path d="m10 17-2.5 3"/></svg>'
    ),
    "/documents": (
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 3.5h6l4 4V20a1 1 0 0 1-1 1H8a2 2 0 0 1-2-2V5.5a2 2 0 0 1 2-2Z"/><path d="M14 3.5V8h4"/><path d="M9 12h6M9 15h6"/></svg>'
    ),
    "/events": (
        '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5" width="16" height="15" rx="3"/><path d="M8 3.5v3M16 3.5v3M4 9h16"/><path d="M9 13h2v2H9z"/></svg>'
    ),
    "/suppliers": (
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9.5 12 5l8 4.5"/><path d="M6 10.5V18h12v-7.5"/><path d="M9 18v-4h6v4"/></svg>'
    ),
    "/users": (
        '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="3.5"/><path d="M5.5 19a6.5 6.5 0 0 1 13 0"/></svg>'
    ),
    "/permissions": (
        '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 4.5v2.2M12 17.3v2.2M4.5 12h2.2M17.3 12h2.2M6.7 6.7l1.6 1.6M15.7 15.7l1.6 1.6M17.3 6.7l-1.6 1.6M8.3 15.7l-1.6 1.6"/></svg>'
    ),
    "/settings": (
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.8 14 5l2.3-.4 1 2.1 2 1.2-.4 2.3 1.2 2-1.2 2 .4 2.3-2 1.2-1 2.1L14 19l-2 1.2L10 19l-2.3.4-1-2.1-2-1.2.4-2.3-1.2-2 1.2-2-.4-2.3 2-1.2 1-2.1L10 5l2-1.2Z"/><circle cx="12" cy="12" r="2.8"/></svg>'
    ),
}

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


def layout(
    title: str,
    body: str,
    current_path: str,
    current_user: dict | None = None,
    allowed_paths: set[str] | None = None,
    notification_badge_count: int = 0,
    theme: str = "light",
) -> bytes:
    if notification_badge_count <= 0 and current_user:
        try:
            notification_badge_count = int(current_user.get("_notification_badge_count", 0)) if isinstance(current_user, dict) else int(current_user["_notification_badge_count"])
        except Exception:
            notification_badge_count = 0

    def user_value(key: str, default: str = "") -> str:
        if not current_user:
            return default
        try:
            value = current_user[key]
        except Exception:
            value = current_user.get(key, default) if isinstance(current_user, dict) else default
        return default if value is None else str(value)

    full_name = user_value("full_name") or user_value("username") or "Kullanıcı"

    nav_links = []
    for path, label in MAIN_NAV_ITEMS:
        if allowed_paths is not None and path not in allowed_paths:
            continue
        css_class = "nav-link active" if path == current_path else "nav-link"
        icon = NAV_ICONS.get(path, "")
        badge_html = (
            f'<span class="nav-badge">{notification_badge_count if notification_badge_count < 100 else "99+"}</span>'
            if path == "/notifications" and notification_badge_count > 0
            else ""
        )
        nav_links.append(
            f'<a class="{css_class}" href="{path}"><span class="nav-link-icon" aria-hidden="true">{icon}</span><span class="nav-link-label">{escape(label)}</span>{badge_html}</a>'
        )
    settings_links = []
    for path, label in SETTINGS_NAV_ITEMS:
        if allowed_paths is not None and path not in allowed_paths:
            continue
        css_class = "nav-sublink active" if path == current_path else "nav-sublink"
        settings_links.append(f'<a class="{css_class}" href="{path}">{escape(label)}</a>')
    if settings_links:
        settings_active = " active" if current_path in {path for path, _ in SETTINGS_NAV_ITEMS} else ""
        settings_icon = NAV_ICONS.get("/settings", "")
        nav_links.append(
            f'<div class="nav-group{settings_active}"><div class="nav-group-label"><span class="nav-link-icon" aria-hidden="true">{settings_icon}</span><span class="nav-link-label">Ayarlar</span></div><div class="nav-sublist">{"".join(settings_links)}</div></div>'
        )
    user_block = ""
    if current_user:
        meta = get_user_sidebar_meta(current_user if isinstance(current_user, dict) else dict(current_user))
        meta_html = f'<span class="sidebar-company-meta">{escape(meta)}</span>' if meta else ""
        user_block = f'<div class="sidebar-user"><strong>{escape(full_name)}</strong>{meta_html}<a class="mini-link" href="/logout">Çıkış</a></div>'
    topbar = ""
    theme_class = ""
    html = f"""
    <!doctype html>
    <html lang="tr" class="{theme_class}">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>{escape(title)} | Pelixi</title>
      <link rel="icon" type="image/png" href="/assets/pelixi-icon.png">
      <link rel="stylesheet" href="/static/style.css">
    </head>
    <body>
      <div class="app-shell">
        <aside class="sidebar">
          <div class="sidebar-brand">
            <img class="brand-lockup-image" src="/assets/pelixi-logo.png" alt="Pelixi logosu" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
            <span class="brand-lockup-fallback" style="display:none;">
              <span class="brand-logo-shell">
                <span class="brand-fallback">P</span>
              </span>
              <span class="brand-lockup">
                <span class="brand-name">PELIXI</span>
                <span class="brand-tagline">İş platformu</span>
              </span>
            </span>
          </div>
          {user_block}
          <nav class="sidebar-nav">{''.join(nav_links)}</nav>
          <div class="sidebar-footer-note">© 2026 Murat Kayacık <span class="footer-separator">•</span> v1.0</div>
        </aside>
        <main class="main-content">{topbar}{body}</main>
      </div>
      <div class="confirm-overlay" data-confirm-overlay hidden>
        <div class="confirm-card" role="dialog" aria-modal="true" aria-labelledby="confirm-title" aria-describedby="confirm-copy">
          <button class="confirm-close" type="button" data-confirm-cancel aria-label="Kapat">×</button>
          <div class="confirm-icon" aria-hidden="true">!</div>
          <h3 id="confirm-title">Silme Onayı</h3>
          <p id="confirm-copy">Bu kayıt silinecek. Devam etmek istediğinize emin misiniz?</p>
          <div class="confirm-actions">
            <button class="mini-link" type="button" data-confirm-cancel>Vazgeç</button>
            <button class="button danger-button" type="button" data-confirm-approve>Sil</button>
          </div>
        </div>
      </div>
      <script>
        (() => {{
          const overlay = document.querySelector('[data-confirm-overlay]');
          const approveButton = overlay?.querySelector('[data-confirm-approve]');
          const titleNode = overlay?.querySelector('#confirm-title');
          const copyNode = overlay?.querySelector('#confirm-copy');
          const cancelButtons = overlay ? Array.from(overlay.querySelectorAll('[data-confirm-cancel]')) : [];
          let pendingForm = null;

          const closeConfirm = () => {{
            if (!overlay) return;
            overlay.hidden = true;
            overlay.classList.remove('is-visible');
            pendingForm = null;
            document.body.classList.remove('confirm-open');
          }};

          closeConfirm();

          const openConfirm = (form) => {{
            if (!overlay) return;
            pendingForm = form;
            const title = form.dataset.confirmTitle || (((form.getAttribute('action') || '').includes('/clear')) ? 'İşlemi Onayla' : 'Silme Onayı');
            const message = form.dataset.confirmMessage || 'Bu kayıt silinecek. Devam etmek istediğinize emin misiniz?';
            const approveLabel = form.dataset.confirmApprove || ((form.getAttribute('action') || '').includes('/clear') ? 'Temizle' : 'Sil');
            if (titleNode) titleNode.textContent = title;
            if (copyNode) copyNode.textContent = message;
            if (approveButton) approveButton.textContent = approveLabel;
            overlay.hidden = false;
            overlay.classList.add('is-visible');
            document.body.classList.add('confirm-open');
            window.setTimeout(() => approveButton?.focus(), 20);
          }};

          approveButton?.addEventListener('click', () => {{
            if (!pendingForm) {{
              closeConfirm();
              return;
            }}
            const form = pendingForm;
            form.dataset.confirmed = '1';
            closeConfirm();
            if (typeof form.requestSubmit === 'function') {{
              form.requestSubmit();
            }} else {{
              form.submit();
            }}
          }});

          cancelButtons.forEach((button) => {{
            button.addEventListener('click', closeConfirm);
          }});

          overlay?.addEventListener('click', (event) => {{
            if (event.target === overlay) closeConfirm();
          }});

          document.addEventListener('keydown', (event) => {{
            if (event.key === 'Escape' && overlay && !overlay.hidden) {{
              closeConfirm();
            }}
          }});

          document.addEventListener('submit', (event) => {{
            const form = event.target;
            if (!(form instanceof HTMLFormElement)) return;
            const action = form.getAttribute('action') || '';
            const hasCustomConfirm = !!form.dataset.confirmMessage;
            if (!hasCustomConfirm && !action.includes('/delete')) return;
            if (form.getAttribute('onsubmit')) return;
            if (form.dataset.confirmed === '1') return;
            event.preventDefault();
            openConfirm(form);
          }}, true);
        }})();
      </script>
    </body>
    </html>
    """
    return html.encode("utf-8")


def auth_layout(title: str, body: str, card_class: str = "") -> bytes:
    card_classes = "auth-card" + (f" {card_class}" if card_class else "")
    html = f"""
    <!doctype html>
    <html lang="tr">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>{escape(title)} | Pelixi</title>
      <link rel="icon" type="image/png" href="/assets/pelixi-icon.png">
      <link rel="stylesheet" href="/static/style.css">
    </head>
    <body class="auth-body">
      <main class="auth-shell">
        <div class="auth-stage">
          <div class="auth-brand">
            <div class="auth-brand-mark">
              <img class="auth-brand-logo" src="/assets/pelixi-logo.png" alt="Pelixi" onerror="this.style.display='none'; this.nextElementSibling.style.display='inline-flex';">
              <span class="auth-brand-fallback" style="display:none;">PELIXI</span>
            </div>
          </div>
          <section class="{card_classes}">
            {body}
          </section>
          <div class="auth-footer-meta">© 2026 Pelixi <span>•</span> Gizlilik <span>•</span> Şartlar</div>
        </div>
      </main>
      <script>
        (() => {{
          const toggles = document.querySelectorAll('[data-password-toggle]');
          toggles.forEach((button) => {{
            button.addEventListener('click', () => {{
              const targetId = button.getAttribute('data-password-toggle');
              const input = targetId ? document.getElementById(targetId) : null;
              if (!input) return;
              const nextType = input.type === 'password' ? 'text' : 'password';
              input.type = nextType;
              button.setAttribute('aria-pressed', nextType === 'text' ? 'true' : 'false');
            }});
          }});

          const forgotLink = document.querySelector('[data-forgot-password-link]');
          const forgotNote = document.querySelector('[data-forgot-password-note]');
          forgotLink?.addEventListener('click', (event) => {{
            event.preventDefault();
            if (!forgotNote) return;
            forgotNote.hidden = !forgotNote.hidden;
          }});
        }})();
      </script>
    </body>
    </html>
    """
    return html.encode("utf-8")


def login_page(error: str = "", next_path: str = "/", info: str = "") -> bytes:
    error_html = f'<p class="form-error">{escape(error)}</p>' if error else ""
    info_html = f'<p class="form-info">{escape(info)}</p>' if info else ""
    body = f"""
    <div class="auth-copy auth-copy-login">
      <p class="eyebrow">Giriş</p>
      <h2>Hoş geldiniz</h2>
      <p>Sisteme devam etmek için kullanıcı adı ve şifrenizi girin.</p>
    </div>
    {info_html}
    {error_html}
    <form method="post" action="/login" class="auth-form auth-form-login">
      <input type="hidden" name="next" value="{escape(next_path)}">
      <label class="field auth-field auth-field-login">
        <span>Kullanıcı Adı veya E-posta</span>
        <div class="auth-input-shell">
          <span class="auth-input-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="3.6"/><path d="M5 19a7 7 0 0 1 14 0"/></svg>
          </span>
          <input id="login-username" type="text" name="username" required placeholder="Örnek: murat veya mail@ornek.com" autocomplete="username">
        </div>
      </label>
        <label class="field auth-field auth-field-login">
          <div class="auth-field-head">
            <span>Şifre</span>
          <a class="auth-field-link" href="#" data-forgot-password-link>Şifremi unuttum</a>
          </div>
          <div class="auth-input-shell">
            <span class="auth-input-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24"><rect x="5.5" y="10" width="13" height="9" rx="2.4"/><path d="M8 10V8a4 4 0 1 1 8 0v2"/></svg>
            </span>
            <input id="login-password" type="password" name="password" required placeholder="Şifreniz" autocomplete="current-password">
            <button class="auth-password-toggle" type="button" data-password-toggle="login-password" aria-label="Şifreyi göster">
              <svg viewBox="0 0 24 24"><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z"/><circle cx="12" cy="12" r="2.8"/></svg>
            </button>
          </div>
          <p class="auth-help-note" data-forgot-password-note hidden>Yönetici ile iletişime geçin.</p>
        </label>
        <div class="auth-inline-note auth-inline-note-login">
          <label class="auth-check">
            <input type="checkbox" name="remember_me" value="1">
            <span>Bu cihazda beni hatırla</span>
        </label>
        </div>
        <button class="button auth-submit" type="submit">
          <span>Giriş Yap</span>
          <span class="auth-submit-arrow" aria-hidden="true">→</span>
        </button>
      </form>
      """
    return auth_layout("Giriş", body)


def setup_page(error: str = "", defaults: dict | None = None) -> bytes:
    defaults = defaults or {}
    error_html = f'<p class="form-error">{escape(error)}</p>' if error else ""
    body = f"""
    <div class="auth-copy">
      <p class="eyebrow">İlk Kurulum</p>
      <h2>Admin kullanıcısını oluşturun</h2>
      <p>Bu ilk kullanıcı sistemin tüm ayarlarını yönetebilecek.</p>
    </div>
    {error_html}
    <form method="post" action="/setup" class="auth-form">
      {input_field("full_name", "Ad Soyad", required=True, value=defaults.get("full_name", ""), placeholder="Örnek: Murat Kayacık")}
      {input_field("username", "Kullanıcı Adı", required=True, value=defaults.get("username", ""), placeholder="Örnek: murat")}
      {input_field("email", "E-posta", input_type="email", value=defaults.get("email", ""), placeholder="ornek@mail.com")}
      {input_field("password", "Şifre", input_type="password", required=True, placeholder="En az 6 karakter")}
      {input_field("password_confirm", "Şifre Tekrar", input_type="password", required=True, placeholder="Şifreyi tekrar yazın")}
      <button class="button auth-submit" type="submit">Kurulumu Tamamla</button>
    </form>
    """
    return auth_layout("İlk Kurulum", body)


def forbidden_page(current_user: dict | None = None, allowed_paths: set[str] | None = None) -> bytes:
    body = """
    <section class="documents-toolbar dashboard-toolbar">
      <div>
        <p class="eyebrow">403</p>
        <h2>Bu alana erişim yetkiniz yok</h2>
        <p>Giriş yaptığınız kullanıcı bu modülü görüntüleyemiyor.</p>
      </div>
      <a class="button" href="/">Dashboard'a dön</a>
    </section>
    """
    return layout("Yetkisiz Erişim", body, "", current_user, allowed_paths)


def users_page(
    users: list,
    roles: list,
    companies: list,
    branches: list,
    edit_item=None,
    current_user: dict | None = None,
    allowed_paths: set[str] | None = None,
    feedback: dict | None = None,
    form_defaults: dict | None = None,
) -> bytes:
    feedback = feedback or {}
    form_defaults = form_defaults or {}
    feedback_html = ""
    if feedback.get("error"):
        feedback_html = f'<p class="form-error inline-feedback">{escape(feedback["error"])}</p>'
    elif feedback.get("info"):
        feedback_html = f'<p class="form-info inline-feedback">{escape(feedback["info"])}</p>'
    body = f"""
    <section class="documents-shell">
      <div class="documents-toolbar">
        <div><p class="eyebrow">Yönetim</p><h2>Kullanıcılar</h2></div>
        <span class="badge">{len(users)} kullanıcı</span>
      </div>
      {feedback_html}
      {quick_user_form(roles, companies, branches, form_defaults)}
      {edit_user_panel(edit_item, roles, companies, branches) if edit_item else ""}
      <div class="documents-table-wrap task-table-panel task-table-panel-active">
        <div class="panel-header compact-header"><h3>Kullanıcı Listesi</h3></div>
        {users_table_header()}
        <div class="task-table">{render_users_table(users)}</div>
      </div>
    </section>
    {task_share_script()}
    {user_form_script()}
    """
    return layout("Kullanıcılar", body, "/users", current_user, allowed_paths)


def user_form_script() -> str:
    return """
    <script>
      (() => {
        const userDialog = document.querySelector('[data-user-create-dialog]');
        if (!userDialog) return;
        const openButtons = document.querySelectorAll('[data-open-user-create]');
        const closeButtons = userDialog.querySelectorAll('[data-close-user-create]');
        const openDialog = () => {
          if (typeof userDialog.showModal === 'function') {
            userDialog.showModal();
          } else {
            userDialog.setAttribute('open', 'open');
          }
        };
        const closeDialog = () => {
          if (typeof userDialog.close === 'function') {
            userDialog.close();
          } else {
            userDialog.removeAttribute('open');
          }
        };
        openButtons.forEach((button) => button.addEventListener('click', openDialog));
        closeButtons.forEach((button) => button.addEventListener('click', closeDialog));
        userDialog.addEventListener('click', (event) => {
          const rect = userDialog.getBoundingClientRect();
          const inside = (
            event.clientX >= rect.left &&
            event.clientX <= rect.right &&
            event.clientY >= rect.top &&
            event.clientY <= rect.bottom
          );
          if (!inside) closeDialog();
        });
      })();
    </script>
    """


def roles_page(
    roles: list,
    edit_item=None,
    current_user: dict | None = None,
    allowed_paths: set[str] | None = None,
    feedback: dict | None = None,
    form_defaults: dict | None = None,
) -> bytes:
    feedback = feedback or {}
    form_defaults = form_defaults or {}
    feedback_html = ""
    if feedback.get("error"):
        feedback_html = f'<p class="form-error inline-feedback">{escape(feedback["error"])}</p>'
    elif feedback.get("info"):
        feedback_html = f'<p class="form-info inline-feedback">{escape(feedback["info"])}</p>'
    body = f"""
    <section class="documents-shell">
      <div class="documents-toolbar">
        <div><p class="eyebrow">Ayarlar</p><h2>Roller</h2></div>
        <span class="badge">{len(roles)} rol</span>
      </div>
      {feedback_html}
      <div class="documents-compact-form user-form-shell">{quick_role_form(form_defaults)}</div>
      {edit_role_panel(edit_item) if edit_item else ""}
      <div class="documents-table-wrap task-table-panel task-table-panel-active">
        <div class="panel-header compact-header"><h3>Rol Listesi</h3></div>
        {roles_table_header()}
        <div class="task-table">{render_roles_table(roles)}</div>
      </div>
    </section>
    """
    return layout("Roller", body, "/roles", current_user, allowed_paths)


def companies_page(
    companies: list,
    edit_item=None,
    current_user: dict | None = None,
    allowed_paths: set[str] | None = None,
    feedback: dict | None = None,
    form_defaults: dict | None = None,
) -> bytes:
    feedback = feedback or {}
    form_defaults = form_defaults or {}
    feedback_html = ""
    if feedback.get("error"):
        feedback_html = f'<p class="form-error inline-feedback">{escape(feedback["error"])}</p>'
    elif feedback.get("info"):
        feedback_html = f'<p class="form-info inline-feedback">{escape(feedback["info"])}</p>'
    body = f"""
    <section class="documents-shell">
      <div class="documents-toolbar">
        <div><p class="eyebrow">Ayarlar</p><h2>Firmalar</h2></div>
        <span class="badge">{len(companies)} firma</span>
      </div>
      {feedback_html}
      <div class="documents-compact-form user-form-shell">{quick_company_form(form_defaults)}</div>
      {edit_company_panel(edit_item) if edit_item else ""}
      <div class="documents-table-wrap task-table-panel task-table-panel-active">
        <div class="panel-header compact-header"><h3>Firma Listesi</h3></div>
        {companies_table_header()}
        <div class="task-table">{render_companies_table(companies)}</div>
      </div>
    </section>
    """
    return layout("Firmalar", body, "/companies", current_user, allowed_paths)


def branches_page(
    branches: list,
    companies: list,
    edit_item=None,
    current_user: dict | None = None,
    allowed_paths: set[str] | None = None,
    feedback: dict | None = None,
    form_defaults: dict | None = None,
) -> bytes:
    feedback = feedback or {}
    form_defaults = form_defaults or {}
    feedback_html = ""
    if feedback.get("error"):
        feedback_html = f'<p class="form-error inline-feedback">{escape(feedback["error"])}</p>'
    elif feedback.get("info"):
        feedback_html = f'<p class="form-info inline-feedback">{escape(feedback["info"])}</p>'
    body = f"""
    <section class="documents-shell">
      <div class="documents-toolbar">
        <div><p class="eyebrow">Ayarlar</p><h2>Şubeler</h2></div>
        <span class="badge">{len(branches)} şube</span>
      </div>
      {feedback_html}
      <div class="documents-compact-form user-form-shell">{quick_branch_form(companies, form_defaults)}</div>
      {edit_branch_panel(edit_item, companies) if edit_item else ""}
      <div class="documents-table-wrap task-table-panel task-table-panel-active">
        <div class="panel-header compact-header"><h3>Şube Listesi</h3></div>
        {branches_table_header()}
        <div class="task-table">{render_branches_table(branches)}</div>
      </div>
    </section>
    """
    return layout("Şubeler", body, "/branches", current_user, allowed_paths)


def notification_settings_page(
    settings: dict,
    current_user: dict | None = None,
    allowed_paths: set[str] | None = None,
    feedback: dict | None = None,
) -> bytes:
    feedback = feedback or {}
    feedback_html = ""
    if feedback.get("error"):
        feedback_html = f'<p class="form-error inline-feedback">{escape(feedback["error"])}</p>'
    elif feedback.get("info"):
        feedback_html = f'<p class="form-info inline-feedback">{escape(feedback["info"])}</p>'
    body = f"""
    <section class="documents-shell">
      <div class="documents-toolbar">
        <div><p class="eyebrow">Ayarlar</p><h2>Bildirim Ayarları</h2></div>
        <span class="badge">Kişisel</span>
      </div>
      {feedback_html}
      <div class="documents-compact-form permission-form-shell notification-settings-shell">
        <form method="post" action="/notification-settings" class="permission-form notification-settings-form">
          <div class="permission-form-top">
            <h3>Bildirim Tercihleri</h3>
            <button class="button" type="submit">Kaydet</button>
          </div>
          <div class="permission-matrix notification-settings-matrix">
            <div class="permission-matrix-head notification-settings-head"><span>Ayar</span><span>Durum</span></div>
            <div class="permission-matrix-body">
              {notification_setting_row("Rozet Göster", "Bekleyen onay talepleri için sidebar rozetini gösterir.", "badge_pending_requests", settings)}
              {notification_setting_row("Onay Bekleyenler", "Size gelen görev ve evrak onay taleplerini listeler.", "approval_items", settings)}
              {notification_setting_row("Gönderdiğim Talepler", "Karşı taraftan cevap bekleyen taleplerinizi gösterir.", "outgoing_items", settings)}
              {notification_setting_row("Görev Uyarıları", "Yaklaşan ve geciken görev bildirimlerini gösterir.", "task_alerts", settings)}
              {notification_setting_row("Evrak Uyarıları", "Yaklaşan ve geciken evrak bildirimlerini gösterir.", "document_alerts", settings)}
              {notification_setting_row("Etkinlik Hatırlatmaları", "Yaklaşan etkinlikleri bildirim merkezine ekler.", "event_reminders", settings)}
            </div>
          </div>
        </form>
      </div>
    </section>
    """
    return layout("Bildirim Ayarları", body, "/notification-settings", current_user, allowed_paths)


def backup_settings_page(
    backups: list[dict],
    summary: dict[str, str],
    current_user: dict | None = None,
    allowed_paths: set[str] | None = None,
    feedback: dict | None = None,
) -> bytes:
    feedback = feedback or {}
    feedback_html = ""
    if feedback.get("error"):
        feedback_html = f'<p class="form-error inline-feedback">{escape(feedback["error"])}</p>'
    elif feedback.get("info"):
        feedback_html = f'<p class="form-info inline-feedback">{escape(feedback["info"])}</p>'
    body = f"""
    <section class="documents-shell">
      <div class="documents-toolbar">
        <div><p class="eyebrow">Ayarlar</p><h2>Yedekleme</h2></div>
        <span class="badge">{len(backups)} yedek</span>
      </div>
      {feedback_html}
      <section class="backup-summary-grid">
        {backup_summary_card("Veritabanı", summary.get("db_name", "-"), summary.get("db_meta", ""))}
        {backup_summary_card("Yedek Klasörü", summary.get("backup_dir_name", "-"), summary.get("backup_dir_meta", ""))}
        {backup_summary_card("Dosyalar", summary.get("uploads_name", "-"), summary.get("uploads_meta", ""))}
      </section>
      <div class="documents-compact-form backup-action-shell">
        <form method="post" action="/backup-settings/create" class="backup-action-form">
          <div class="backup-action-copy">
            <h3>Manuel Yedek Al</h3>
            <p>Mevcut veritabanının anlık bir kopyasını güvenli şekilde oluşturur.</p>
          </div>
          <button class="button" type="submit">Yedek Oluştur</button>
        </form>
      </div>
      <div class="documents-table-wrap task-table-panel task-table-panel-active">
        <div class="panel-header compact-header"><h3>Yedek Listesi</h3></div>
        {backup_table_header()}
        <div class="task-table">{render_backup_table(backups)}</div>
      </div>
    </section>
    """
    return layout("Yedekleme", body, "/backup-settings", current_user, allowed_paths)


def file_settings_page(
    settings: dict,
    summary: dict[str, str],
    current_user: dict | None = None,
    allowed_paths: set[str] | None = None,
    feedback: dict | None = None,
) -> bytes:
    feedback = feedback or {}
    feedback_html = ""
    if feedback.get("error"):
        feedback_html = f'<p class="form-error inline-feedback">{escape(feedback["error"])}</p>'
    elif feedback.get("info"):
        feedback_html = f'<p class="form-info inline-feedback">{escape(feedback["info"])}</p>'
    allowed_extensions = row_value(settings, "allowed_extensions") or ""
    max_size = row_value(settings, "max_file_size_mb", 10)
    body = f"""
    <section class="documents-shell">
      <div class="documents-toolbar">
        <div><p class="eyebrow">Ayarlar</p><h2>Dosya Ayarları</h2></div>
        <span class="badge">Genel</span>
      </div>
      {feedback_html}
      <section class="backup-summary-grid file-settings-summary-grid">
        {backup_summary_card("Yükleme Klasörü", summary.get("uploads_name", "-"), summary.get("uploads_meta", ""))}
        {backup_summary_card("İzin Verilen Türler", summary.get("extensions_name", "-"), summary.get("extensions_meta", ""))}
        {backup_summary_card("Maksimum Boyut", summary.get("max_size_name", "-"), summary.get("max_size_meta", ""))}
      </section>
      <div class="documents-compact-form permission-form-shell file-settings-shell">
        <form method="post" action="/file-settings" class="permission-form file-settings-form">
          <div class="permission-form-top">
            <h3>Yükleme Kuralları</h3>
            <button class="button" type="submit">Kaydet</button>
          </div>
          <div class="file-settings-grid">
            {input_field("allowed_extensions", "İzin Verilen Uzantılar", value=allowed_extensions, required=True, placeholder="Örnek: .pdf, .docx, .xlsx, .jpg")}
            {input_field("max_file_size_mb", "Maksimum Boyut (MB)", input_type="number", value=str(max_size), required=True, placeholder="Örnek: 10", extra_attrs='min="1" max="100" step="1"')}
          </div>
          <p class="file-settings-help">Uzantıları virgülle ayırın. Bu kurallar şu an toplantı dosya yüklemelerinde uygulanır; ileride diğer modüllere de aynı şekilde yansır.</p>
          <div class="file-settings-preview">
            {render_file_extension_tags(allowed_extensions)}
          </div>
        </form>
      </div>
    </section>
    """
    return layout("Dosya Ayarları", body, "/file-settings", current_user, allowed_paths)


def backup_summary_card(label: str, title: str, detail: str) -> str:
    return (
        f'<article class="backup-summary-card">'
        f'<span>{escape(label)}</span>'
        f'<strong>{escape(title)}</strong>'
        f'<p>{escape(detail)}</p>'
        f'</article>'
    )


def render_file_extension_tags(raw_value: str) -> str:
    parts = [part.strip().lower() for part in str(raw_value or "").split(",")]
    items = []
    seen: set[str] = set()
    for part in parts:
        if not part:
            continue
        normalized = part if part.startswith(".") else f".{part}"
        if normalized in seen:
            continue
        seen.add(normalized)
        items.append(f'<span class="status-chip neutral file-extension-tag">{escape(normalized)}</span>')
    return "".join(items) or '<span class="empty-state inline-empty">Henüz uzantı tanımlanmadı.</span>'


def backup_table_header() -> str:
    return '<div class="task-header-row backup-header-row"><span>Dosya</span><span>Tür</span><span>Tarih</span><span>Boyut</span><span>İşlem</span></div>'


def render_backup_table(items: list[dict]) -> str:
    if not items:
        return '<p class="empty-state">Henüz yedek yok.</p>'
    return "".join(render_backup_row(item) for item in items)


def render_backup_row(item: dict) -> str:
    backup_type = "Manuel" if int(item.get("is_manual", 0)) else "Otomatik"
    return (
        '<article class="backup-row">'
        '<div class="backup-main">'
        f'<div class="task-cell task-cell-title"><h4>{escape(item.get("name", "-"))}</h4></div>'
        f'<div class="task-cell"><span class="priority-chip medium">{escape(backup_type)}</span></div>'
        f'<div class="task-cell">{escape(format_datetime(item.get("modified_at")))}</div>'
        f'<div class="task-cell">{escape(item.get("size_label", "-"))}</div>'
        f'<div class="task-cell user-actions"><a class="mini-link" href="/backup-settings/download?name={escape(item.get("name", ""))}">İndir</a></div>'
        '</div>'
        '</article>'
    )


def audit_logs_page(
    items: list,
    filters: dict | None = None,
    module_options: list[str] | None = None,
    user_options: list[str] | None = None,
    action_options: list[str] | None = None,
    current_user: dict | None = None,
    allowed_paths: set[str] | None = None,
    feedback: dict | None = None,
) -> bytes:
    feedback = feedback or {}
    filters = filters or {}
    module_options = module_options or []
    user_options = user_options or []
    action_options = action_options or []
    feedback_html = ""
    if feedback.get("error"):
        feedback_html = f'<p class="form-error inline-feedback">{escape(feedback["error"])}</p>'
    elif feedback.get("info"):
        feedback_html = f'<p class="form-info inline-feedback">{escape(feedback["info"])}</p>'
    module_select_options = {"": "Tüm Modüller"}
    for option in module_options:
        module_select_options[option] = option
    user_select_options = {"": "Tüm Kullanıcılar"}
    for option in user_options:
        user_select_options[option] = option
    action_select_options = {"": "Tüm İşlemler"}
    for option in action_options:
        action_select_options[option] = option
    search_class = 'class="audit-filter-input is-empty"' if not filters.get("q", "") else 'class="audit-filter-input"'
    module_class = "audit-filter-select is-empty" if not filters.get("module", "") else "audit-filter-select"
    user_class = "audit-filter-select is-empty" if not filters.get("actor", "") else "audit-filter-select"
    action_class = "audit-filter-select is-empty" if not filters.get("action", "") else "audit-filter-select"
    date_from_class = 'class="audit-date-input is-empty"' if not filters.get("date_from", "") else 'class="audit-date-input"'
    date_to_class = 'class="audit-date-input is-empty"' if not filters.get("date_to", "") else 'class="audit-date-input"'
    quick_links = audit_quick_links(filters)
    body = f"""
    <section class="documents-shell">
      <div class="documents-toolbar">
        <div><p class="eyebrow">Ayarlar</p><h2>Kayıt Geçmişi</h2></div>
        <span class="badge">{len(items)} kayıt</span>
      </div>
      {feedback_html}
      <div class="audit-quick-row">
        <div class="meeting-tab-bar audit-quick-links">{quick_links}</div>
        <div class="audit-quick-actions">
          <a class="button secondary audit-quick-button" href="/audit-logs">Temizle</a>
          <a class="button secondary audit-quick-button" href="/audit-logs/export?{escape(urlencode({k: v for k, v in filters.items() if v}))}">CSV Dışa Aktar</a>
        </div>
      </div>
      <div class="documents-compact-form audit-filter-shell">
        <form method="get" action="/audit-logs" class="quick-task-form compact-inline-form audit-filter-form">
          <div class="audit-filter-grid">
            {input_field("q", "Genel Arama", value=filters.get("q", ""), placeholder="Kullanıcı, işlem veya detay ara", extra_attrs=search_class)}
            {select_field("module", "Modül", module_select_options, filters.get("module", ""), css_class=module_class)}
            {select_field("actor", "Kullanıcı", user_select_options, filters.get("actor", ""), css_class=user_class)}
            {select_field("action", "İşlem", action_select_options, filters.get("action", ""), css_class=action_class)}
            {input_field("date_from", "Başlangıç Tarihi", input_type="date", value=filters.get("date_from", ""), extra_attrs=date_from_class)}
            {input_field("date_to", "Bitiş Tarihi", input_type="date", value=filters.get("date_to", ""), extra_attrs=date_to_class)}
            <button class="button" type="submit">Filtrele</button>
          </div>
        </form>
      </div>
      <div class="documents-table-wrap task-table-panel task-table-panel-active">
        <div class="panel-header compact-header"><h3>Son İşlemler</h3></div>
        {audit_logs_table_header()}
        <div class="task-table audit-log-table">{render_audit_logs_table(items)}</div>
      </div>
    </section>
    """
    return layout("Kayıt Geçmişi", body, "/audit-logs", current_user, allowed_paths)


def audit_quick_links(filters: dict) -> str:
    today = date.today()
    presets = [
        ("Bugün", today.isoformat(), today.isoformat()),
        ("Son 7 Gün", (today - timedelta(days=6)).isoformat(), today.isoformat()),
        ("Bu Ay", today.replace(day=1).isoformat(), today.isoformat()),
    ]
    links = []
    for label, start_date, end_date in presets:
        query = {key: value for key, value in filters.items() if key not in {"date_from", "date_to"} and value}
        query["date_from"] = start_date
        query["date_to"] = end_date
        is_active = filters.get("date_from") == start_date and filters.get("date_to") == end_date
        active_class = " active" if is_active else ""
        links.append(f'<a class="filter-chip{active_class}" href="/audit-logs?{escape(urlencode(query))}"><span>{escape(label)}</span></a>')
    return "".join(links)


def audit_logs_table_header() -> str:
    return '<div class="task-header-row audit-header-row"><span>Tarih</span><span>Kullanıcı</span><span>Modül</span><span>İşlem</span><span>Detay</span></div>'


def render_audit_logs_table(items: list) -> str:
    if not items:
        return '<p class="empty-state">Henüz kayıt geçmişi yok.</p>'
    return "".join(render_audit_log_row(item) for item in items)


def render_audit_log_row(item) -> str:
    details = row_value(item, "details") or "-"
    return (
        '<article class="audit-row">'
        '<div class="audit-main">'
        f'<div class="task-cell">{escape(format_datetime(row_value(item, "created_at") or ""))}</div>'
        f'<div class="task-cell"><strong>{escape(row_value(item, "actor_name") or "Sistem")}</strong></div>'
        f'<div class="task-cell"><span class="status-chip neutral">{escape(row_value(item, "module_name") or "-")}</span></div>'
        f'<div class="task-cell"><span class="priority-chip medium">{escape(row_value(item, "action") or "-")}</span></div>'
        f'<div class="task-cell audit-detail-cell">{escape(details)}</div>'
        '</div>'
        '</article>'
    )


def permissions_page(
    roles: list,
    permissions: list,
    selected_role_code: str,
    selected_permission_codes: set[str],
    current_user: dict | None = None,
    allowed_paths: set[str] | None = None,
    feedback: dict | None = None,
) -> bytes:
    feedback = feedback or {}
    feedback_html = ""
    if feedback.get("error"):
        feedback_html = f'<p class="form-error inline-feedback">{escape(feedback["error"])}</p>'
    elif feedback.get("info"):
        feedback_html = f'<p class="form-info inline-feedback">{escape(feedback["info"])}</p>'

    role_tabs = []
    for role in roles:
        active = " active" if role["code"] == selected_role_code else ""
        role_tabs.append(
            f'<a class="filter-chip{active}" href="/permissions?role={escape(role["code"])}"><span>{escape(role["name"])}</span></a>'
        )

    grouped: dict[str, dict[str, dict]] = {}
    module_labels = {
        "tasks": "Görevler",
        "meetings": "Toplantılar",
        "documents": "Evraklar",
        "events": "Etkinlikler",
        "suppliers": "Tedarikçiler",
        "attachments": "Dosyalar",
        "users": "Kullanıcılar",
        "roles": "Roller",
    }
    action_labels = {
        "view": "Görüntüle",
        "create": "Ekle",
        "edit": "Düzenle",
        "delete": "Sil",
        "manage": "Yönet",
        "upload": "Yükle",
    }
    action_order = ["view", "create", "edit", "delete", "manage", "upload"]
    for item in permissions:
        code = str(item["code"])
        action = code.split(".", 1)[1] if "." in code else ""
        grouped.setdefault(item["module_name"], {})[action] = {"code": code, "name": item["name"]}

    rows_html = []
    for module_name, action_map in grouped.items():
        cells = []
        for action in action_order:
            item = action_map.get(action)
            if item:
                checked = " checked" if item["code"] in selected_permission_codes else ""
                cells.append(
                    f'<label class="permission-matrix-check"><input type="checkbox" name="permission_code" value="{escape(item["code"])}"{checked}><span>{escape(action_labels[action])}</span></label>'
                )
            else:
                cells.append('<span class="permission-empty">-</span>')
        rows_html.append(
            f'<div class="permission-matrix-row"><div class="permission-matrix-module">{escape(module_labels.get(module_name, module_name.title()))}</div>{"".join(f"<div class=\"permission-matrix-cell\">{cell}</div>" for cell in cells)}</div>'
        )

    header_html = "".join(
        f'<span>{escape(action_labels[action])}</span>' for action in action_order
    )

    body = f"""
    <section class="documents-shell">
      <div class="documents-toolbar">
        <div><p class="eyebrow">Yönetim</p><h2>Yetkilendirme</h2></div>
        <span class="badge">{len(roles)} rol</span>
      </div>
      {feedback_html}
      <div class="meeting-tab-bar">{"".join(role_tabs)}</div>
      <div class="documents-compact-form permission-form-shell">
        <form method="post" action="/permissions" class="permission-form">
          <input type="hidden" name="role_code" value="{escape(selected_role_code)}">
          <div class="permission-form-top">
            <h3>{escape(next((role["name"] for role in roles if role["code"] == selected_role_code), selected_role_code))} Yetkileri</h3>
            <button class="button" type="submit">Kaydet</button>
          </div>
          <div class="permission-matrix">
            <div class="permission-matrix-head"><span>Modül</span>{header_html}</div>
            <div class="permission-matrix-body">{"".join(rows_html)}</div>
          </div>
        </form>
      </div>
    </section>
    """
    return layout("Yetkilendirme", body, "/permissions", current_user, allowed_paths)


def notification_setting_row(title: str, detail: str, key: str, settings: dict) -> str:
    checked = " checked" if int(settings.get(key, 0)) else ""
    return (
        '<div class="notification-setting-row">'
        f'<div class="notification-setting-copy"><strong>{escape(title)}</strong><p>{escape(detail)}</p></div>'
        f'<label class="toggle-switch"><input type="checkbox" name="{escape(key)}" value="1"{checked}><span class="toggle-slider"></span></label>'
        '</div>'
    )


def quick_role_form(defaults: dict | None = None) -> str:
    defaults = defaults or {}
    return f"""
    <form method="post" action="/roles" class="quick-task-form compact-inline-form">
      <div class="quick-user-grid quick-user-grid-main">
        {input_field("name", "Rol Adı", required=True, value=defaults.get("name", ""), placeholder="Örnek: Koordinatör")}
        {input_field("description", "Kısa Açıklama", value=defaults.get("description", ""), placeholder="Rolün kullanım amacını kısa yazın")}
        <button class="button" type="submit">Rol Ekle</button>
      </div>
    </form>
    """


def quick_company_form(defaults: dict | None = None) -> str:
    defaults = defaults or {}
    return f"""
    <form method="post" action="/companies" class="quick-task-form compact-inline-form">
      <div class="quick-user-grid quick-user-grid-meta company-form-grid">
        {input_field("name", "Firma Adı", required=True, value=defaults.get("name", ""), placeholder="Örnek: Pelixi Eğitim")}
        {input_field("code", "Kısa Kod", required=True, value=defaults.get("code", ""), placeholder="Örnek: pelixi")}
        <button class="button" type="submit">Firma Ekle</button>
      </div>
    </form>
    """


def companies_table_header() -> str:
    return '<div class="task-header-row user-header-row company-header-row"><span>Firma</span><span>Kod</span><span>Şube</span><span>Kullanıcı</span><span>İşlem</span></div>'


def render_companies_table(items: list) -> str:
    if not items:
        return '<p class="empty-state">Henüz firma yok.</p>'
    return "".join(render_company_row(item) for item in items)


def render_company_row(item) -> str:
    actions = (
        f'<div class="row-actions">'
        f'<a class="mini-link" href="/companies?edit={item["id"]}">Düzenle</a>'
        f'<form method="post" action="/companies/delete" class="inline-form" data-confirm-title="Firma Sil" data-confirm-message="Bu firma silinecek. Devam etmek istiyor musunuz?" data-confirm-approve="Sil">'
        f'<input type="hidden" name="id" value="{item["id"]}">'
        f'<button class="mini-link danger" type="submit">Sil</button></form>'
        f'</div>'
    )
    branch_count = int(row_value(item, "branch_count", 0) or 0)
    user_count = int(row_value(item, "user_count", 0) or 0)
    return f'<article class="user-row"><div class="user-main company-main"><div class="task-cell task-cell-title"><h4>{escape(row_value(item, "name") or "-")}</h4></div><div class="task-cell">{escape(row_value(item, "code") or "-")}</div><div class="task-cell"><span class="status-chip neutral">{branch_count} şube</span></div><div class="task-cell"><span class="status-chip neutral">{user_count} kullanıcı</span></div><div class="task-cell user-actions">{actions}</div></div></article>'


def edit_company_panel(item) -> str:
    return f"""
    <div class="documents-edit-bar">
      <div class="panel-header"><h3>Firmayı Düzenle</h3><a class="text-link" href="/companies">Vazgeç</a></div>
      <form method="post" action="/companies/update" class="quick-task-form compact-inline-form">
        <input type="hidden" name="id" value="{item["id"]}">
        <div class="quick-user-grid quick-user-grid-meta company-form-grid">
          {input_field("name", "Firma Adı", required=True, value=row_value(item, "name") or "")}
          {input_field("code", "Kısa Kod", required=True, value=row_value(item, "code") or "")}
          <button class="button" type="submit">Güncelle</button>
        </div>
      </form>
    </div>
    """


def quick_branch_form(companies: list, defaults: dict | None = None) -> str:
    defaults = defaults or {}
    company_options = {str(row["id"]): row["name"] for row in companies}
    return f"""
    <form method="post" action="/branches" class="quick-task-form compact-inline-form">
      <div class="quick-user-grid quick-user-grid-meta branch-form-grid">
        {select_field("company_id", "Firma", company_options, str(defaults.get("company_id", "")))}
        {input_field("name", "Şube Adı", required=True, value=defaults.get("name", ""), placeholder="Örnek: Nilüfer Kampüs")}
        {input_field("code", "Kısa Kod", required=True, value=defaults.get("code", ""), placeholder="Örnek: nilufer")}
        <button class="button" type="submit">Şube Ekle</button>
      </div>
    </form>
    """


def branches_table_header() -> str:
    return '<div class="task-header-row user-header-row branch-header-row"><span>Şube</span><span>Firma</span><span>Kod</span><span>Kullanıcı</span><span>İşlem</span></div>'


def render_branches_table(items: list) -> str:
    if not items:
        return '<p class="empty-state">Henüz şube yok.</p>'
    return "".join(render_branch_row(item) for item in items)


def render_branch_row(item) -> str:
    actions = (
        f'<div class="row-actions">'
        f'<a class="mini-link" href="/branches?edit={item["id"]}">Düzenle</a>'
        f'<form method="post" action="/branches/delete" class="inline-form" data-confirm-title="Şube Sil" data-confirm-message="Bu şube silinecek. Devam etmek istiyor musunuz?" data-confirm-approve="Sil">'
        f'<input type="hidden" name="id" value="{item["id"]}">'
        f'<button class="mini-link danger" type="submit">Sil</button></form>'
        f'</div>'
    )
    user_count = int(row_value(item, "user_count", 0) or 0)
    return f'<article class="user-row"><div class="user-main branch-main"><div class="task-cell task-cell-title"><h4>{escape(row_value(item, "name") or "-")}</h4></div><div class="task-cell">{escape(row_value(item, "company_name") or "-")}</div><div class="task-cell">{escape(row_value(item, "code") or "-")}</div><div class="task-cell"><span class="status-chip neutral">{user_count} kullanıcı</span></div><div class="task-cell user-actions">{actions}</div></div></article>'


def edit_branch_panel(item, companies: list) -> str:
    company_options = {str(row["id"]): row["name"] for row in companies}
    return f"""
    <div class="documents-edit-bar">
      <div class="panel-header"><h3>Şubeyi Düzenle</h3><a class="text-link" href="/branches">Vazgeç</a></div>
      <form method="post" action="/branches/update" class="quick-task-form compact-inline-form">
        <input type="hidden" name="id" value="{item["id"]}">
        <div class="quick-user-grid quick-user-grid-meta branch-form-grid">
          {select_field("company_id", "Firma", company_options, str(row_value(item, "company_id") or ""))}
          {input_field("name", "Şube Adı", required=True, value=row_value(item, "name") or "")}
          {input_field("code", "Kısa Kod", required=True, value=row_value(item, "code") or "")}
          <button class="button" type="submit">Güncelle</button>
        </div>
      </form>
    </div>
    """


def roles_table_header() -> str:
    return '<div class="task-header-row user-header-row"><span>Rol</span><span>Kod</span><span>Açıklama</span><span>İşlem</span></div>'


def render_roles_table(items: list) -> str:
    if not items:
        return '<p class="empty-state">Henüz rol yok.</p>'
    return "".join(render_role_row(item) for item in items)


def render_role_row(item) -> str:
    description = row_value(item, "description") or "-"
    is_system = bool(row_value(item, "is_system", 0))
    action_html = (
        '<span class="mini-link subtle disabled">Sistem</span>'
        if is_system
        else f'<div class="row-actions"><a class="mini-link" href="/roles?edit={escape(row_value(item, "code") or "")}">Düzenle</a><form method="post" action="/roles/delete" class="inline-form"><input type="hidden" name="code" value="{escape(row_value(item, "code") or "")}"><button class="mini-link danger" type="submit">Sil</button></form></div>'
    )
    return f'<article class="user-row"><div class="user-main"><div class="task-cell task-cell-title"><h4>{escape(row_value(item, "name") or "-")}</h4></div><div class="task-cell">{escape(row_value(item, "code") or "-")}</div><div class="task-cell">{escape(description)}</div><div class="task-cell user-actions">{action_html}</div></div></article>'


def edit_role_panel(item) -> str:
    return f"""
    <div class="documents-edit-bar">
      <div class="panel-header"><h3>Rolü Düzenle</h3><a class="text-link" href="/roles">Vazgeç</a></div>
      <form method="post" action="/roles/update" class="quick-task-form compact-inline-form">
        <input type="hidden" name="code" value="{escape(row_value(item, "code") or "")}">
        <div class="quick-user-grid quick-user-grid-main">
          {input_field("name", "Rol Adı", required=True, value=row_value(item, "name") or "")}
          {input_field("description", "Kısa Açıklama", value=row_value(item, "description") or "", placeholder="Rolün kullanım amacını kısa yazın")}
          <button class="button" type="submit">Güncelle</button>
        </div>
      </form>
    </div>
    """


def quick_user_form(roles: list, companies: list, branches: list, defaults: dict | None = None) -> str:
    defaults = defaults or {}
    role_options = {row["code"]: row["name"] for row in roles}
    status_options = {"1": "Aktif", "0": "Pasif"}
    selected_company_ids = parse_id_list(defaults.get("company_ids")) or parse_id_list(defaults.get("company_id"))
    selected_branch_ids = parse_id_list(defaults.get("branch_ids")) or parse_id_list(defaults.get("branch_id"))
    return f"""
    <div class="task-create-launcher">
      <button class="task-create-button" type="button" data-open-user-create>
        <span class="task-create-icon">+</span>
        <span>Yeni kullanıcı ekle</span>
      </button>
    </div>
    <dialog class="task-create-dialog user-create-dialog" data-user-create-dialog>
      <div class="task-create-dialog-card user-create-dialog-card">
        <div class="panel-header task-create-header">
          <div><h3>Yeni Kullanıcı</h3></div>
          <button class="task-dialog-close" type="button" data-close-user-create aria-label="Kapat">×</button>
        </div>
        <form method="post" action="/users" class="quick-task-form user-create-form">
          <div class="quick-user-grid quick-user-grid-main user-create-grid-main">
            {input_field("full_name", "Ad Soyad", required=True, value=defaults.get("full_name", ""), placeholder="Örnek: Ayşe Demir")}
            {input_field("username", "Kullanıcı Adı", required=True, value=defaults.get("username", ""), placeholder="Örnek: ayse")}
            {input_field("email", "E-posta", input_type="email", value=defaults.get("email", ""), placeholder="ornek@mail.com")}
            {input_field("phone", "Telefon", value=defaults.get("phone", ""), placeholder="Örnek: 5551234567")}
          </div>
          <div class="quick-user-grid quick-user-grid-meta user-create-grid-meta">
            {input_field("password", "Şifre", input_type="password", required=True, placeholder="En az 6 karakter")}
            {company_multi_field(companies, selected_company_ids)}
            {branch_multi_field(branches, selected_branch_ids)}
            {select_field("role_code", "Rol", role_options, defaults.get("role_code", "ogretmen"))}
            {select_field("is_active", "Durum", status_options, defaults.get("is_active", "1"))}
          </div>
          <div class="task-create-actions">
            <button class="mini-link subtle" type="button" data-close-user-create>Vazgeç</button>
            <button class="button" type="submit">Ekle</button>
          </div>
        </form>
      </div>
    </dialog>
    """


def edit_user_panel(item, roles: list, companies: list, branches: list) -> str:
    role_options = {row["code"]: row["name"] for row in roles}
    status_options = {"1": "Aktif", "0": "Pasif"}
    selected_role = (row_value(item, "role_codes") or "ogretmen").split(",")[0]
    selected_company_ids = parse_id_list(row_value(item, "company_ids") or row_value(item, "company_id"))
    selected_branch_ids = parse_id_list(row_value(item, "branch_ids") or row_value(item, "branch_id"))
    return f"""
    <div class="documents-edit-bar">
      <div class="panel-header"><h3>Kullanıcıyı Düzenle</h3><a class="text-link" href="/users">Vazgeç</a></div>
      <form method="post" action="/users/update" class="quick-task-form compact-inline-form">
        <input type="hidden" name="id" value="{item["id"]}">
        <div class="quick-user-grid quick-user-grid-main">
          {input_field("full_name", "Ad Soyad", required=True, value=row_value(item, "full_name") or "")}
          {input_field("username", "Kullanıcı Adı", required=True, value=row_value(item, "username") or "")}
          {input_field("email", "E-posta", input_type="email", value=row_value(item, "email") or "")}
          {input_field("phone", "Telefon", value=row_value(item, "phone") or "")}
        </div>
        <div class="quick-user-grid quick-user-grid-meta">
          {input_field("password", "Yeni Şifre", input_type="password", placeholder="Değişmeyecekse boş bırakın")}
          {company_multi_field(companies, selected_company_ids)}
          {branch_multi_field(branches, selected_branch_ids)}
          {select_field("role_code", "Rol", role_options, selected_role)}
          {select_field("is_active", "Durum", status_options, "1" if row_value(item, "is_active", 1) else "0")}
          <button class="button" type="submit">Güncelle</button>
        </div>
      </form>
    </div>
    """


def users_table_header() -> str:
    return '<div class="task-header-row user-header-row"><span>Ad Soyad</span><span>Kullanıcı Adı</span><span>Firma</span><span>Şube</span><span>Rol</span><span>Durum</span><span>İşlem</span></div>'


def render_users_table(items: list) -> str:
    if not items:
        return '<p class="empty-state">Henüz kullanıcı yok.</p>'
    return "".join(render_user_row(item) for item in items)


def render_user_row(item) -> str:
    status_label = "Aktif" if row_value(item, "is_active", 1) else "Pasif"
    status_class = "success" if row_value(item, "is_active", 1) else "neutral"
    is_admin_role = "admin" in str(row_value(item, "role_codes") or "").split(",")
    toggle_label = "Pasif Yap" if row_value(item, "is_active", 1) else "Aktif Et"
    toggle_action = (
        f'<form method="post" action="/users/toggle-active" class="inline-form"><input type="hidden" name="id" value="{item["id"]}"><button class="mini-link subtle" type="submit">{toggle_label}</button></form>'
        if not is_admin_role
        else '<span class="mini-link subtle disabled">Sabit</span>'
    )
    company_summary = row_value(item, "company_names") or row_value(item, "company_name") or "-"
    branch_summary = row_value(item, "branch_names") or row_value(item, "branch_name") or "-"
    return f'<article class="user-row"><div class="user-main"><div class="task-cell task-cell-title"><h4>{escape(row_value(item, "full_name") or "-")}</h4></div><div class="task-cell">{escape(row_value(item, "username") or "-")}</div><div class="task-cell">{escape(company_summary)}</div><div class="task-cell">{escape(branch_summary)}</div><div class="task-cell"><span class="priority-chip medium">{escape(row_value(item, "role_names") or "-")}</span></div><div class="task-cell"><span class="status-chip {status_class}">{status_label}</span></div><div class="task-cell user-actions"><a class="mini-link" href="/users?edit={item["id"]}">Düzenle</a>{toggle_action}</div></div></article>'


def dashboard_page(summary: dict, tasks: list, documents: list, meetings: list, suppliers: list, events: list, alerts: list, current_user: dict | None = None, allowed_paths: set[str] | None = None, theme: str = "light") -> bytes:
    body = f"""
    <section class="documents-toolbar dashboard-toolbar">
      <div>
        <p class="eyebrow">Genel Bakış</p>
        <h2>Dashboard</h2>
      </div>
      <a class="button secondary dashboard-toolbar-button" href="/tasks">Görevlere Git</a>
    </section>
    <section class="stats-grid dashboard-stats-grid">
      {stat_card("Bekleyen Görev", summary["pending_tasks"], "Bugün odaklanılacak işler", "tone-1")}
      {stat_card("Yaklaşan Evrak", summary["upcoming_documents"], "7 gün içindeki tarihler", "tone-2")}
      {stat_card("Toplantı Notu", summary["meeting_count"], "Kayıtlı son notlar", "tone-3")}
      {stat_card("Etkinlik", summary["event_count"], "Yaklaşan etkinlik kaydı", "tone-4")}
    </section>
    {alert_panel(alerts)}
    <section class="dashboard-panels-grid">
      {record_panel("Bugünün Görevleri", tasks, render_task_item, "tone-task")}
      {record_panel("Son Toplantı Notları", meetings, render_meeting_item, "tone-meeting")}
      {record_panel("Yaklaşan Evraklar", documents, render_document_item, "tone-document")}
      {record_panel("Yaklaşan Etkinlikler", events, render_event_card, "tone-event")}
    </section>
    """
    return layout("Dashboard", body, "/", current_user, allowed_paths, theme=theme)


def notifications_page(groups: list[dict], total_count: int, current_user: dict | None = None, allowed_paths: set[str] | None = None, theme: str = "light") -> bytes:
    group_html = "".join(render_notification_group(group) for group in groups)
    if not group_html:
        group_html = '<section class="panel notification-panel"><p class="empty-state">Şu an yeni bildirim yok.</p></section>'
    body = f"""
    <section class="documents-shell notifications-shell">
      <div class="documents-toolbar">
        <div><p class="eyebrow">Merkez</p><h2>Bildirimler</h2></div>
        <span class="badge">{total_count} bildirim</span>
      </div>
      <section class="notification-summary-grid">
        {notification_summary_card("Onay", sum(len(group.get("items", [])) for group in groups if group.get("tone") == "approval"), "Bekleyen kararlar", "approval")}
        {notification_summary_card("Takip", sum(len(group.get("items", [])) for group in groups if group.get("tone") in {"danger", "warn"}), "Geciken ve yaklaşanlar", "warn")}
        {notification_summary_card("Paylaşım", sum(len(group.get("items", [])) for group in groups if group.get("tone") == "info"), "Size gelen/giden işler", "info")}
      </section>
      <div class="notification-groups">{group_html}</div>
    </section>
    """
    return layout("Bildirimler", body, "/notifications", current_user, allowed_paths, theme=theme)


def notification_summary_card(title: str, value: int, detail: str, tone: str) -> str:
    return f'<article class="notification-summary-card {escape(tone)}"><span>{escape(title)}</span><strong>{value}</strong><p>{escape(detail)}</p></article>'


def render_notification_group(group: dict) -> str:
    items = group.get("items", [])
    if not items:
        return ""
    rows = "".join(render_notification_item(item) for item in items)
    tone = escape(group.get("tone", "neutral"))
    return (
        f'<section class="panel notification-panel {tone}">'
        f'<div class="panel-header"><h3>{escape(group["title"])}</h3><span class="badge">{len(items)}</span></div>'
        f'<div class="notification-list">{rows}</div>'
        f'</section>'
    )


def render_notification_item(item: dict) -> str:
    tone = escape(item.get("tone", "neutral"))
    href = escape(item.get("href", "#"))
    meta = escape(item.get("meta", ""))
    action = escape(item.get("action", "Aç"))
    return (
        f'<article class="notification-item {tone}">'
        f'<span class="notification-dot" aria-hidden="true"></span>'
        f'<div class="notification-copy"><strong>{escape(item["title"])}</strong><p>{escape(item.get("detail", ""))}</p><small>{meta}</small></div>'
        f'<a class="mini-link" href="{href}">{action}</a>'
        f'</article>'
    )


def alert_panel(items: list) -> str:
    rows = "".join(render_alert_item(item) for item in items)
    if not rows:
        rows = '<p class="empty-state">Bugün için kritik bir uyarı görünmüyor.</p>'
    return f'<section class="panel alert-panel"><div class="panel-header"><h3>Uyarılar ve Hatırlatmalar</h3></div><div class="alert-list">{rows}</div></section>'


def render_alert_item(item: dict) -> str:
    tone = escape(item.get("tone", "neutral"))
    meta = escape(item.get("meta", ""))
    return f'<article class="alert-item {tone}"><div class="alert-copy"><h4>{escape(item["title"])}</h4><p>{escape(item["detail"])}</p></div><div class="alert-meta">{meta}</div></article>'


def search_results_page(query: str, groups: list[dict], current_user: dict | None = None, allowed_paths: set[str] | None = None) -> bytes:
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
    return layout("Arama", body, "", current_user, allowed_paths)


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


def stat_card(label: str, value: int, detail: str, tone: str = "tone-1") -> str:
    return f'<article class="stat-card {escape(tone)}"><p>{escape(label)}</p><strong>{value}</strong><span>{escape(detail)}</span></article>'


def record_panel(title: str, items: list, item_renderer, tone: str = "") -> str:
    tone_class = f" {escape(tone)}" if tone else ""
    count_label = f'<span class="badge">{len(items)} kayıt</span>' if items else ""
    return (
        f'<section class="panel dashboard-record-panel{tone_class}">'
        f'<div class="panel-header"><h3>{escape(title)}</h3>{count_label}</div>'
        f'<div class="dashboard-record-body"><div class="record-list">{render_list(items, item_renderer)}</div></div>'
        f'</section>'
    )


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


def textarea_field(name: str, label: str, value: str = "", placeholder: str = "", rows: int = 4, extra_class: str = "") -> str:
    placeholder_attr = f' placeholder="{escape(placeholder)}"' if placeholder else ""
    class_attr = f' class="{escape(extra_class)}"' if extra_class else ""
    return f'<label class="field{class_attr}"><span>{escape(label)}</span><textarea name="{escape(name)}" rows="{rows}"{placeholder_attr}>{escape(value)}</textarea></label>'


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


def format_date_range(start_value: str | None, end_value: str | None) -> str:
    start_label = format_date(start_value)
    end_raw = end_value or start_value
    end_label = format_date(end_raw)
    if not start_value:
        return "-"
    if not end_raw or start_value == end_raw:
        return start_label
    return f"{start_label} - {end_label}"


def row_value(item, key: str, default=""):
    try:
        value = item[key]
    except Exception:
        return default
    return default if value is None else value


def parse_id_list(value) -> list[int]:
    if value is None:
        return []
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = [part.strip() for part in str(value).split(",")]
    parsed: list[int] = []
    for raw_item in raw_items:
        try:
            normalized = int(raw_item)
        except (TypeError, ValueError):
            continue
        if normalized not in parsed:
            parsed.append(normalized)
    return parsed


def _share_field(label: str, placeholder: str, input_name: str, items: list, selected_ids: list[int] | None = None, item_label_key: str = "full_name", fallback_key: str = "username") -> str:
    selected_ids = selected_ids or []
    selected_set = {int(item_id) for item_id in selected_ids}
    selected_names = []
    chips = []
    for item in items:
        item_id = int(item["id"])
        checked = " checked" if item_id in selected_set else ""
        active = " event-level-chip active" if item_id in selected_set else " event-level-chip"
        display_name = row_value(item, item_label_key) or row_value(item, fallback_key) or label
        if item_id in selected_set:
            selected_names.append(display_name)
        chips.append(
            f'<label class="{active}"><input type="checkbox" name="{escape(input_name)}" value="{item_id}"{checked}><span>{escape(display_name)}</span></label>'
        )
    if not items:
        summary = f"Aktif {label.lower()} yok"
        placeholder_flag = "1"
    elif selected_names:
        summary = ", ".join(selected_names[:2])
        if len(selected_names) > 2:
            summary += f" +{len(selected_names) - 2}"
        placeholder_flag = "0"
    else:
        summary = placeholder
        placeholder_flag = "1"
    return f'<div class="field event-level-field task-share-field"><span>{escape(label)}</span><details class="event-level-dropdown task-share-dropdown" data-task-share-dropdown data-placeholder-text="{escape(placeholder)}"><summary class="event-level-summary" data-task-share-summary data-placeholder="{placeholder_flag}">{escape(summary)}</summary><div class="event-level-group">{"".join(chips)}</div></details></div>'


def user_share_field(users: list, selected_ids: list[int] | None = None) -> str:
    return _share_field("Paylaş", "Kişi seçin", "share_user_ids", users, selected_ids, "full_name", "username")


def role_share_field(roles: list, selected_ids: list[int] | None = None) -> str:
    return _share_field("Rol", "Rol seçin", "share_role_ids", roles, selected_ids, "name", "code")


def company_multi_field(companies: list, selected_ids: list[int] | None = None) -> str:
    return _share_field("Firma", "Firma seçin", "company_ids", companies, selected_ids, "name", "code")


def branch_multi_field(branches: list, selected_ids: list[int] | None = None) -> str:
    prepared = []
    for item in branches:
        branch = dict(item)
        branch_name = row_value(item, "name")
        branch["display_name"] = branch_name
        prepared.append(branch)
    return _share_field("Şube", "Şube seçin", "branch_ids", prepared, selected_ids, "display_name", "code")


def tasks_page(active_items: list, completed_items: list, share_users: list, share_roles: list, owner_requests: list | None = None, request_history: list | None = None, edit_item=None, edit_can_manage_directly: bool = True, active_filter: str = "all", filter_counts: dict | None = None, feedback: dict | None = None, current_user: dict | None = None, allowed_paths: set[str] | None = None, activity_view: str = "week") -> bytes:
    filter_counts = filter_counts or {}
    owner_requests = owner_requests or []
    request_history = request_history or []
    feedback = feedback or {}
    feedback_html = ""
    if feedback.get("error"):
        feedback_html = f'<p class="form-error inline-feedback">{escape(feedback["error"])}</p>'
    elif feedback.get("info"):
        feedback_html = f'<p class="form-info inline-feedback">{escape(feedback["info"])}</p>'
    auto_open_create = "1" if feedback.get("error") else "0"
    task_overview = render_task_overview_v2(active_items, completed_items, current_user, activity_view)
    body = f"""
    <section class="documents-shell tasks-shell-v2">
      {task_overview}
      {feedback_html}
      {quick_task_form_v3(share_users, share_roles, auto_open_create, show_launcher=False)}
      {task_request_panel(owner_requests)}
      {task_request_history_panel(request_history)}
      {edit_task_panel_v3(edit_item, share_users, share_roles, edit_can_manage_directly) if edit_item else ''}
      <div class="documents-table-wrap task-table-panel task-table-panel-active task-list-shell">
        <div class="panel-header panel-header-spacious task-panel-toolbar">
          <div class="task-panel-toolbar-main">
            <h3>Aktif Görevler</h3>
            {task_filter_bar(active_filter, filter_counts)}
          </div>
          <span class="badge">{len(active_items)} görev</span>
        </div>
        {task_table_header_v3(False)}
        <div class="task-table">{render_task_table_v3(active_items, False)}</div>
      </div>
      <div class="documents-table-wrap task-table-panel task-table-panel-completed task-list-shell">
        <div class="panel-header panel-header-spacious"><div><p class="mini-eyebrow">Arşiv</p><h3>Tamamlanan Görevler</h3></div><span class="badge">{len(completed_items)} görev</span></div>
        {task_table_header_v3(True)}
        <div class="task-table">{render_task_table_v3(completed_items, True)}</div>
      </div>
    </section>
    {task_share_script()}
    """
    return layout("Görevler", body, "/tasks", current_user, allowed_paths)


def render_task_overview_v2(active_items: list, completed_items: list, current_user: dict | None = None, activity_view: str = "week") -> str:
    full_name = ""
    if isinstance(current_user, dict):
        full_name = str(current_user.get("full_name") or current_user.get("username") or "").strip()
    first_name = full_name.split()[0] if full_name else "Merhaba"
    greeting = f"Merhaba {escape(first_name)}"

    today_iso = date.today().isoformat()
    active_total = len(active_items)
    completed_total = len(completed_items)
    total_all = active_total + completed_total
    due_today = sum(1 for item in active_items if row_value(item, "due_date") == today_iso)
    overdue = sum(
        1
        for item in active_items
        if row_value(item, "due_date") and row_value(item, "due_date") < today_iso
    )
    completion_rate = int(round((completed_total / total_all) * 100)) if total_all else 0

    subtitle_parts = []
    subtitle_parts.append(f"Bugün {due_today} teslim görevin var.")
    subtitle_parts.append(f"{overdue} görev gecikmiş durumda." if overdue else "Geciken görev görünmüyor.")
    subtitle = " ".join(subtitle_parts)

    cards = [
        task_overview_card("Aktif", "Aktif Görev", str(active_total), "Açık iş yükü", "tone-primary", "✓"),
        task_overview_card("Bugün", "Bugün Teslim", str(due_today), "Gün içi odak", "tone-neutral", "☼"),
        task_overview_card("Acil", "Geciken Görev", str(overdue), "Önceliklendirme gerekli", "tone-danger", "!"),
        task_overview_progress_card("Hedef", "Tamamlanma", f"{completion_rate}%", max(6, completion_rate), "Toplam akış", "◎"),
    ]

    return f"""
    <section class="task-overview-shell">
      <div class="task-overview-top">
        <div class="task-overview-copy">
          <div class="task-overview-path">Çalışma Alanı <span>›</span> Görevler</div>
          <h2>{greeting} <span aria-hidden="true">👋</span></h2>
          <p>{escape(subtitle)}</p>
        </div>
        <div class="task-overview-actions">
          <form class="task-overview-search" method="get" action="/search">
            <span class="task-overview-search-icon" aria-hidden="true">⌕</span>
            <input type="search" name="q" value="" placeholder="Görev, kişi veya etiket ara..." aria-label="Görev arama" />
            <button class="task-overview-search-button" type="submit">Ara</button>
          </form>
          <button class="task-create-button task-create-button-top" type="button" data-open-task-create>
            <span class="task-create-icon">+</span>
            <span>Yeni görev ekle</span>
          </button>
        </div>
      </div>
      <div class="task-overview-board">
        {''.join(cards)}
        {task_weekly_activity_card(active_items, completed_items, activity_view)}
        {task_priority_breakdown_card(active_items)}
      </div>
    </section>
    """


def task_overview_card(tag: str, title: str, value: str, note: str, tone: str, icon: str) -> str:
    return (
        f'<article class="task-overview-card {escape(tone)}">'
        '<div class="task-overview-headrow">'
        f'<span class="task-overview-glyph" aria-hidden="true">{escape(icon)}</span>'
        f'<span class="task-overview-tag">{escape(tag)}</span>'
        '</div>'
        f'<h4>{escape(title)}</h4>'
        f'<strong>{escape(value)}</strong>'
        f'<p>{escape(note)}</p>'
        f'</article>'
    )


def task_overview_progress_card(tag: str, title: str, value: str, progress: int, note: str, icon: str) -> str:
    safe_progress = max(0, min(100, progress))
    return (
        '<article class="task-overview-card tone-progress">'
        '<div class="task-overview-headrow">'
        f'<span class="task-overview-glyph" aria-hidden="true">{escape(icon)}</span>'
        f'<span class="task-overview-tag">{escape(tag)}</span>'
        '</div>'
        f'<h4>{escape(title)}</h4>'
        f'<strong>{escape(value)}</strong>'
        f'<div class="task-overview-progress"><span style="width:{safe_progress}%"></span></div>'
        f'<p>{escape(note)}</p>'
        '</article>'
    )


def task_weekly_activity_card(active_items: list, completed_items: list, activity_view: str = "week") -> str:
    safe_view = "month" if activity_view == "month" else "week"
    today = date.today()

    if safe_view == "month":
        labels = ["1.Hf", "2.Hf", "3.Hf", "4.Hf", "5.Hf"]
        due_counts = [0] * 5
        done_counts = [0] * 5

        def month_bucket(day_obj: date) -> int:
            return min(4, (day_obj.day - 1) // 7)

        for item in active_items:
            raw_date = row_value(item, "due_date")
            if not raw_date:
                continue
            try:
                due_date = date.fromisoformat(raw_date)
            except ValueError:
                continue
            if due_date.year == today.year and due_date.month == today.month:
                due_counts[month_bucket(due_date)] += 1

        for item in completed_items:
            raw_completed = row_value(item, "completed_at")
            if not raw_completed:
                continue
            try:
                done_date = datetime.fromisoformat(str(raw_completed)).date()
            except ValueError:
                try:
                    done_date = date.fromisoformat(str(raw_completed)[:10])
                except ValueError:
                    continue
            if done_date.year == today.year and done_date.month == today.month:
                done_counts[month_bucket(done_date)] += 1
    else:
        labels = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
        due_counts = [0] * 7
        done_counts = [0] * 7
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        for item in active_items:
            raw_date = row_value(item, "due_date")
            if not raw_date:
                continue
            try:
                due_date = date.fromisoformat(raw_date)
            except ValueError:
                continue
            if week_start <= due_date <= week_end:
                due_counts[due_date.weekday()] += 1

        for item in completed_items:
            raw_completed = row_value(item, "completed_at")
            if not raw_completed:
                continue
            try:
                done_date = datetime.fromisoformat(str(raw_completed)).date()
            except ValueError:
                try:
                    done_date = date.fromisoformat(str(raw_completed)[:10])
                except ValueError:
                    continue
            if week_start <= done_date <= week_end:
                done_counts[done_date.weekday()] += 1

    max_value = max(max(due_counts or [0]), max(done_counts or [0]), 1)
    axis_top = max(3, max_value)
    axis_mid = max(1, round(axis_top / 2))
    axis_labels = [axis_top, axis_mid, 0]
    rows = []
    for idx, label in enumerate(labels):
        due_height = max(8, round((due_counts[idx] / max_value) * 92)) if due_counts[idx] else 6
        done_height = max(8, round((done_counts[idx] / max_value) * 92)) if done_counts[idx] else 6
        rows.append(
            '<div class="task-mini-chart-day">'
            '<div class="task-mini-chart-bars">'
            f'<span class="muted" style="height:{due_height}px"></span>'
            f'<span class="brand" style="height:{done_height}px"></span>'
            '</div>'
            f'<small>{label}</small>'
            '</div>'
        )

    toggle_links = []
    for value, label in (("week", "Hafta"), ("month", "Ay")):
        css = "task-view-toggle active" if value == safe_view else "task-view-toggle"
        toggle_links.append(f'<a class="{css}" href="/tasks?activity={value}">{label}</a>')

    return (
        '<section class="task-analytics-card">'
        '<div class="task-analytics-head">'
        '<div><h3>Haftalık Aktivite</h3><p>Teslim ve tamamlanan görev ritmi</p></div>'
        f'<div class="task-analytics-controls"><div class="task-analytics-legend"><span><i class="muted"></i>Teslim</span><span><i class="brand"></i>Tamamlanan</span></div><div class="task-view-toggle-group">{"".join(toggle_links)}</div></div>'
        '</div>'
        '<div class="task-mini-chart-shell">'
        f'<div class="task-mini-chart-axis">{"".join(f"<span>{value}</span>" for value in axis_labels)}</div>'
        f'<div class="task-mini-chart">{"".join(rows)}</div>'
        '</div>'
        '</section>'
    )


def task_priority_breakdown_card(active_items: list) -> str:
    counts = {
        "high": 0,
        "medium": 0,
        "low": 0,
    }
    for item in active_items:
        priority = str(row_value(item, "priority") or "medium")
        if priority in counts:
            counts[priority] += 1

    total = sum(counts.values()) or 1
    circ = 2 * 3.14159 * 52
    order = [("high", "Yüksek"), ("medium", "Orta"), ("low", "Düşük")]
    offsets = []
    running = 0.0
    for key, _label in order:
        portion = counts[key] / total
        length = circ * portion
        offsets.append((key, length, running))
        running += length

    rings = []
    for key, length, running in offsets:
        css = {"high": "ring-high", "medium": "ring-medium", "low": "ring-low"}[key]
        rings.append(
            f'<circle class="{css}" cx="60" cy="60" r="52" stroke-dasharray="{length:.2f} {circ:.2f}" stroke-dashoffset="-{running:.2f}"></circle>'
        )

    legend = []
    for key, label in order:
        legend.append(
            f'<div class="task-priority-row {escape(key)}"><span>{escape(label)}</span><strong>{counts[key]}</strong></div>'
        )

    return (
        '<section class="task-analytics-card task-priority-card">'
        '<div class="task-analytics-head">'
        '<div><h3>Öncelik Dağılımı</h3><p>Aktif görevlerin öncelik dengesi</p></div>'
        '</div>'
        '<div class="task-priority-body">'
        '<svg class="task-priority-donut" viewBox="0 0 120 120" aria-hidden="true">'
        '<circle class="task-priority-track" cx="60" cy="60" r="52"></circle>'
        f'{"".join(rings)}'
        '</svg>'
        f'<div class="task-priority-legend">{"".join(legend)}</div>'
        '</div>'
        '</section>'
    )


def task_request_panel(items: list) -> str:
    if not items:
        return ""
    rows = []
    for item in items:
        request_label = "Düzenleme talebi" if item["request_type"] == "update" else "Silme talebi"
        rows.append(
            f'<article class="task-request-row">'
            f'<div class="task-request-copy"><strong>{escape(item["requester_name"])}</strong><span>{escape(item["task_title"])}</span><p>{escape(request_label)} • {escape(item["detail"])}</p><small>{escape(item.get("summary", ""))}</small></div>'
            f'<div class="task-request-actions">'
            f'<form method="post" action="/tasks/requests/approve" class="inline-form"><input type="hidden" name="request_id" value="{item["id"]}"><button class="mini-link" type="submit">Onayla</button></form>'
            f'<form method="post" action="/tasks/requests/reject" class="inline-form"><input type="hidden" name="request_id" value="{item["id"]}"><button class="mini-link danger" type="submit">Reddet</button></form>'
            f'</div>'
            f'</article>'
        )
    return f'<div class="documents-table-wrap task-request-panel"><div class="panel-header"><h3>Onay Bekleyen Talepler</h3><span class="badge">{len(items)} talep</span></div><div class="task-request-list">{"".join(rows)}</div></div>'


def task_request_history_panel(items: list) -> str:
    if not items:
        return ""
    rows = []
    for item in items:
        delete_control = (
            f'<label class="history-select-box"><input type="checkbox" name="request_ids" value="{item["id"]}"><span></span></label>'
            if item.get("can_delete")
            else '<span class="history-select-lock" title="Bekleyen talepler silinemez">-</span>'
        )
        delete_button = (
            f'<form method="post" action="/tasks/requests/history/delete" class="inline-form history-inline-delete" data-confirm-title="Geçmiş Kaydını Sil" data-confirm-message="Bu talep geçmişi kaydı silinecek. Devam etmek istiyor musunuz?" data-confirm-approve="Sil"><input type="hidden" name="request_id" value="{item["id"]}"><button class="mini-link danger" type="submit">Sil</button></form>'
            if item.get("can_delete")
            else ""
        )
        rows.append(
            f'<article class="task-request-row history">'
            f'<div class="task-history-select">{delete_control}</div>'
            f'<div class="task-request-copy">'
            f'<strong>{escape(item["task_title"])}</strong>'
            f'<span>{escape(item["role_label"])} • {escape(item["request_label"])}</span>'
            f'<p>{escape(item["detail"])}</p>'
            f'<small>{escape(item.get("summary", ""))}</small>'
            f'</div>'
            f'<div class="task-request-actions">'
            f'<span class="task-history-time">{escape(format_datetime(item.get("updated_at")) or "-")}</span>'
            f'<span class="task-history-status {escape(item["status"])}">{escape(item["status_label"])}</span>'
            f'{delete_button}'
            f'</div>'
            f'</article>'
        )
    return (
        '<details class="documents-table-wrap task-request-panel history-panel">'
        '<summary class="task-history-summary">'
        '<span>Talep Geçmişi</span>'
        f'<span class="badge">{len(items)} kayıt</span>'
        '</summary>'
        '<div class="task-history-toolbar">'
        '<button class="mini-link subtle" type="button" data-history-select-toggle>Geçmişi Sil</button>'
        '<div class="task-history-bulk-actions" data-history-bulk-actions hidden>'
        '<form method="post" action="/tasks/requests/history/delete" class="inline-form" data-history-selection-form data-confirm-title="Seçili Geçmişi Sil" data-confirm-message="Seçtiğiniz talep geçmişi kayıtları silinecek. Devam etmek istiyor musunuz?" data-confirm-approve="Sil">'
        '<button class="mini-link danger" type="submit">Seçilenleri Sil</button>'
        '</form>'
        '<form method="post" action="/tasks/requests/history/clear" class="inline-form" data-confirm-title="Tüm Geçmişi Temizle" data-confirm-message="Sonuçlanan tüm talep geçmişi silinecek. Bu işlem geri alınamaz." data-confirm-approve="Temizle">'
        '<button class="mini-link danger ghost" type="submit">Tüm Geçmişi Sil</button>'
        '</form>'
        '<button class="mini-link subtle" type="button" data-history-cancel>Vazgeç</button>'
        '</div>'
        '</div>'
        f'<div class="task-request-list" data-history-list>{"".join(rows)}</div>'
        '</details>'
    )


def document_request_panel(items: list) -> str:
    if not items:
        return ""
    rows = []
    for item in items:
        request_label = "Düzenleme talebi" if item["request_type"] == "update" else "Silme talebi"
        rows.append(
            f'<article class="task-request-row">'
            f'<div class="task-request-copy"><strong>{escape(item["requester_name"])}</strong><span>{escape(item["document_title"])}</span><p>{escape(request_label)} • {escape(item["detail"])}</p><small>{escape(item.get("summary", ""))}</small></div>'
            f'<div class="task-request-actions">'
            f'<form method="post" action="/documents/requests/approve" class="inline-form"><input type="hidden" name="request_id" value="{item["id"]}"><button class="mini-link" type="submit">Onayla</button></form>'
            f'<form method="post" action="/documents/requests/reject" class="inline-form"><input type="hidden" name="request_id" value="{item["id"]}"><button class="mini-link danger" type="submit">Reddet</button></form>'
            f'</div>'
            f'</article>'
        )
    return f'<div class="documents-table-wrap task-request-panel"><div class="panel-header"><h3>Onay Bekleyen Evrak Talepleri</h3><span class="badge">{len(items)} talep</span></div><div class="task-request-list">{"".join(rows)}</div></div>'


def document_request_history_panel(items: list) -> str:
    if not items:
        return ""
    rows = []
    for item in items:
        delete_control = (
            f'<label class="history-select-box"><input type="checkbox" name="request_ids" value="{item["id"]}"><span></span></label>'
            if item.get("can_delete")
            else '<span class="history-select-lock" title="Bekleyen talepler silinemez">-</span>'
        )
        delete_button = (
            f'<form method="post" action="/documents/requests/history/delete" class="inline-form history-inline-delete" data-confirm-title="Geçmiş Kaydını Sil" data-confirm-message="Bu evrak talep geçmişi kaydı silinecek. Devam etmek istiyor musunuz?" data-confirm-approve="Sil"><input type="hidden" name="request_id" value="{item["id"]}"><button class="mini-link danger" type="submit">Sil</button></form>'
            if item.get("can_delete")
            else ""
        )
        rows.append(
            f'<article class="task-request-row history">'
            f'<div class="task-history-select">{delete_control}</div>'
            f'<div class="task-request-copy">'
            f'<strong>{escape(item["document_title"])}</strong>'
            f'<span>{escape(item["role_label"])} • {escape(item["request_label"])}</span>'
            f'<p>{escape(item["detail"])}</p>'
            f'<small>{escape(item.get("summary", ""))}</small>'
            f'</div>'
            f'<div class="task-request-actions">'
            f'<span class="task-history-time">{escape(format_datetime(item.get("updated_at")) or "-")}</span>'
            f'<span class="task-history-status {escape(item["status"])}">{escape(item["status_label"])}</span>'
            f'{delete_button}'
            f'</div>'
            f'</article>'
        )
    return (
        '<details class="documents-table-wrap task-request-panel history-panel">'
        '<summary class="task-history-summary">'
        '<span>Talep Geçmişi</span>'
        f'<span class="badge">{len(items)} kayıt</span>'
        '</summary>'
        '<div class="task-history-toolbar">'
        '<button class="mini-link subtle" type="button" data-history-select-toggle>Geçmişi Sil</button>'
        '<div class="task-history-bulk-actions" data-history-bulk-actions hidden>'
        '<form method="post" action="/documents/requests/history/delete" class="inline-form" data-history-selection-form data-confirm-title="Seçili Geçmişi Sil" data-confirm-message="Seçtiğiniz evrak geçmişi kayıtları silinecek. Devam etmek istiyor musunuz?" data-confirm-approve="Sil">'
        '<button class="mini-link danger" type="submit">Seçilenleri Sil</button>'
        '</form>'
        '<form method="post" action="/documents/requests/history/clear" class="inline-form" data-confirm-title="Tüm Geçmişi Temizle" data-confirm-message="Sonuçlanan tüm evrak talep geçmişi silinecek. Bu işlem geri alınamaz." data-confirm-approve="Temizle">'
        '<button class="mini-link danger ghost" type="submit">Tüm Geçmişi Sil</button>'
        '</form>'
        '<button class="mini-link subtle" type="button" data-history-cancel>Vazgeç</button>'
        '</div>'
        '</div>'
        f'<div class="task-request-list" data-history-list>{"".join(rows)}</div>'
        '</details>'
    )


def task_filter_bar(active_filter: str, filter_counts: dict[str, int]) -> str:
    chips = []
    for value, label in TASK_FILTERS:
        css = "filter-chip active" if value == active_filter else "filter-chip"
        href = "/tasks" if value == "all" else f"/tasks?filter={value}"
        chips.append(f'<a class="{css}" href="{href}"><span>{escape(label)}</span><strong>{filter_counts.get(value, 0)}</strong></a>')
    return f'<div class="filter-bar">{"".join(chips)}</div>'


def quick_task_form_v3(share_users: list, share_roles: list, auto_open: str = "0", show_launcher: bool = True) -> str:
    launcher = f"""
    <div class="task-create-launcher">
      <button class="task-create-button" type="button" data-open-task-create>
        <span class="task-create-icon">+</span>
        <span>Yeni görev ekle</span>
      </button>
    </div>
    """ if show_launcher else ""
    return f"""
    {launcher}
    <dialog class="task-create-dialog" data-task-create-dialog data-auto-open="{auto_open}">
      <div class="task-create-dialog-card">
        <div class="panel-header task-create-header">
          <div><h3>Yeni Görev</h3></div>
          <button class="task-dialog-close" type="button" data-close-task-create aria-label="Kapat">×</button>
        </div>
        <form method="post" action="/tasks" class="quick-task-form task-create-form">
          <div class="quick-task-grid quick-task-grid-v2 task-create-grid">
            {input_field("title", "Görev", required=True, placeholder="Örnek: Veli toplantısı notlarını hazırla")}
            {input_field("responsible_person", "Sorumlu", placeholder="Şimdilik boş kalabilir")}
            {user_share_field(share_users)}
            {role_share_field(share_roles)}
            {select_field("priority", "Öncelik", PRIORITY_LABELS, "medium")}
            {input_field("due_date", "Son Tarih", input_type="date", value="")}
          </div>
          {textarea_field("description", "Kısa Açıklama", "", "İstersen kısa not ekleyebilirsin", rows=3, extra_class="compact-note-field")}
          <div class="task-create-actions">
            <button class="mini-link subtle" type="button" data-close-task-create>Vazgeç</button>
            <button class="button" type="submit">Ekle</button>
          </div>
        </form>
      </div>
    </dialog>
    """


def edit_task_panel_v3(item, share_users: list, share_roles: list, can_manage_directly: bool = True) -> str:
    selected_share_ids = row_value(item, "_share_user_ids", [])
    selected_role_ids = row_value(item, "_share_role_ids", [])
    share_field_html = user_share_field(share_users, selected_share_ids) if can_manage_directly else f'<div class="field task-share-readonly"><small class="readonly-tip">Paylaşılan kullanıcı bu alanı değiştiremez. Düzenleme isteği görev sahibine gider.</small><span>Paylaşım</span><div class="readonly-value">{escape(row_value(item, "_share_summary", "-"))}</div></div>'
    role_field_html = role_share_field(share_roles, selected_role_ids) if can_manage_directly else f'<div class="field task-share-readonly"><small class="readonly-tip">Rol paylaşımı yalnızca görev sahibi tarafından değiştirilir.</small><span>Rol</span><div class="readonly-value">{escape(", ".join(row_value(item, "_share_role_names", [])) or "-")}</div></div>'
    submit_label = "Güncelle" if can_manage_directly else "Onay İçin Gönder"
    return f"""
    <div class="panel quick-task-panel">
      <div class="panel-header"><h3>Görevi Düzenle</h3><a class="text-link" href="/tasks">Vazgeç</a></div>
      <form method="post" action="/tasks/update" class="quick-task-form">
        <input type="hidden" name="id" value="{item['id']}">
        <div class="quick-task-grid quick-task-grid-v2">
          {input_field("title", "Görev", required=True, value=item["title"])}
          {input_field("responsible_person", "Sorumlu", value=row_value(item, "responsible_person") or "", placeholder="Boş bırakılabilir")}
          {share_field_html}
          {role_field_html}
          {select_field("priority", "Öncelik", PRIORITY_LABELS, item["priority"])}
          {input_field("due_date", "Son Tarih", input_type="date", value=row_value(item, "due_date") or "")}
          <button class="button" type="submit">{submit_label}</button>
        </div>
        {textarea_field("description", "Kısa Açıklama", row_value(item, "description") or "", "İstersen kısa not ekleyebilirsin", rows=2, extra_class="compact-note-field")}
      </form>
    </div>
    """


def task_table_header_v3(completed: bool) -> str:
    actions = "" if completed else "İşlem"
    return f'<div class="task-header-row task-header-row-v2"><span></span><span>Görev</span><span>Sorumlu</span><span>Paylaşım</span><span>Öncelik</span><span>Son Tarih</span><span>Tamamlanma</span><span>{actions}</span></div>'


def render_task_table_v3(items: list, completed: bool) -> str:
    if not items:
        return '<p class="empty-state">Henüz tamamlanan görev yok.</p>' if completed else '<p class="empty-state">Aktif görev bulunmuyor.</p>'
    return "".join(render_task_row_v3(item, completed) for item in items)


def render_task_row_v3(item, completed: bool) -> str:
    priority_label = translate_label(item["priority"], PRIORITY_LABELS)
    checked = " checked" if completed else ""
    row_class = "task-row done" if completed else "task-row"
    actions = completed_task_actions(item) if completed else active_task_actions(item)
    share_count = int(row_value(item, "_share_count", 0) or 0)
    role_count = int(row_value(item, "_share_role_count", 0) or 0)
    share_summary = row_value(item, "_share_summary", "-")
    share_tooltip = row_value(item, "_share_tooltip", "")
    shared_from = row_value(item, "_shared_from", "")
    share_badge = (
        '<span class="task-share-badge muted">Özel</span>' if share_count == 0 and role_count == 0
        else f'<span class="task-share-badge">{share_count} kişi • {role_count} rol</span>' if share_count and role_count
        else f'<span class="task-share-badge">{share_count} kişi</span>' if share_count
        else f'<span class="task-share-badge">{role_count} rol</span>'
    )
    share_detail = (
        "Yalnızca size özel"
        if share_count == 0 and role_count == 0
        else share_summary
    )
    share_html = (
        f'<div class="task-cell task-cell-share" title="{escape(share_tooltip)}">'
        f'{share_badge}'
        f'<span class="task-share-text">{escape(share_detail)}</span>'
        f'{f"<span class=\"task-share-origin\">{escape(shared_from)} tarafından paylaşıldı</span>" if shared_from else ""}'
        f'</div>'
    )
    return f'<article class="{row_class}"><form class="task-toggle-form" method="post" action="/tasks/toggle"><input type="hidden" name="id" value="{item["id"]}"><input type="hidden" name="next_status" value="{"pending" if completed else "completed"}"><button class="task-check{checked}" type="submit" aria-label="Görev durumunu değiştir"></button></form><div class="task-main task-main-v2"><div class="task-cell task-cell-title"><h4>{escape(item["title"])}</h4></div><div class="task-cell">{escape(row_value(item, "responsible_person", "-"))}</div>{share_html}<div class="task-cell task-cell-priority"><span class="priority-chip {escape(item["priority"])}">{escape(priority_label)}</span></div><div class="task-cell task-cell-date">{escape(format_date(row_value(item, "due_date")))}</div><div class="task-cell task-cell-date">{escape(format_datetime(row_value(item, "completed_at")))}</div><div class="task-cell task-cell-actions">{actions}</div></div></article>'


def active_task_actions(item) -> str:
    pending_request_type = row_value(item, "_pending_request_type", "")
    pending_owner = row_value(item, "_pending_request_owner", "")
    if pending_request_type:
        label = "Düzenleme onayı bekliyor" if pending_request_type == "update" else "Silme onayı bekliyor"
        title = f"{label} - {pending_owner}" if pending_owner else label
        short_label = "Düzenleme bekliyor" if pending_request_type == "update" else "Silme bekliyor"
        owner_html = f'<span class="pending-task-owner">{escape(pending_owner)}</span>' if pending_owner else ""
        return f'<div class="row-actions pending-task-action"><span class="pending-task-badge" title="{escape(title)}">{escape(short_label)}</span>{owner_html}</div>'
    return f'<div class="row-actions"><a class="mini-link" href="/tasks?edit={item["id"]}">Düzenle</a><form method="post" action="/tasks/delete" class="inline-form"><input type="hidden" name="id" value="{item["id"]}"><button class="mini-link danger" type="submit">Sil</button></form></div>'


def completed_task_actions(item) -> str:
    return (
        f'<div class="row-actions">'
        f'<form method="post" action="/tasks/toggle" class="inline-form"><input type="hidden" name="id" value="{item["id"]}"><input type="hidden" name="next_status" value="pending"><button class="mini-link" type="submit">Geri Al</button></form>'
        f'<form method="post" action="/tasks/delete" class="inline-form"><input type="hidden" name="id" value="{item["id"]}"><button class="mini-link danger" type="submit">Sil</button></form>'
        f'</div>'
    )


def task_share_script() -> str:
    return """
    <script>
      (() => {
        const taskDialog = document.querySelector('[data-task-create-dialog]');
        if (taskDialog) {
          const openButtons = document.querySelectorAll('[data-open-task-create]');
          const closeButtons = taskDialog.querySelectorAll('[data-close-task-create]');
          const openDialog = () => {
            if (typeof taskDialog.showModal === 'function') {
              taskDialog.showModal();
            } else {
              taskDialog.setAttribute('open', 'open');
            }
          };
          const closeDialog = () => {
            if (typeof taskDialog.close === 'function') {
              taskDialog.close();
            } else {
              taskDialog.removeAttribute('open');
            }
          };
          openButtons.forEach((button) => button.addEventListener('click', openDialog));
          closeButtons.forEach((button) => button.addEventListener('click', closeDialog));
          taskDialog.addEventListener('click', (event) => {
            const rect = taskDialog.getBoundingClientRect();
            const inside = (
              event.clientX >= rect.left &&
              event.clientX <= rect.right &&
              event.clientY >= rect.top &&
              event.clientY <= rect.bottom
            );
            if (!inside) closeDialog();
          });
          if (taskDialog.dataset.autoOpen === '1') {
            openDialog();
          }
        }
        const syncChipState = (input) => {
          const chip = input.closest('.event-level-chip');
          if (chip) chip.classList.toggle('active', input.checked);
        };
        const updateSummary = (details) => {
          const summary = details.querySelector('[data-task-share-summary]');
          const checked = [...details.querySelectorAll('input[type="checkbox"]:checked')];
          if (!summary) return;
          if (!checked.length) {
            summary.textContent = details.dataset.placeholderText || 'Seçim yapın';
            summary.dataset.placeholder = '1';
            return;
          }
          const labels = checked.map((input) => input.closest('label')?.innerText?.trim() || '').filter(Boolean);
          summary.textContent = labels.length > 2 ? `${labels.slice(0, 2).join(', ')} +${labels.length - 2}` : labels.join(', ');
          summary.dataset.placeholder = '0';
        };
        document.querySelectorAll('[data-task-share-dropdown]').forEach((details) => {
          updateSummary(details);
          details.querySelectorAll('input[type="checkbox"]').forEach((input) => {
            syncChipState(input);
            input.addEventListener('change', () => {
              syncChipState(input);
              updateSummary(details);
            });
          });
        });

        document.querySelectorAll('.history-panel').forEach((panel) => {
          const toggle = panel.querySelector('[data-history-select-toggle]');
          const cancel = panel.querySelector('[data-history-cancel]');
          const bulk = panel.querySelector('[data-history-bulk-actions]');
          const list = panel.querySelector('[data-history-list]');
          const selectionForm = panel.querySelector('[data-history-selection-form]');
          if (!toggle || !bulk || !list || !selectionForm) return;

          const setSelectionMode = (enabled) => {
            panel.classList.toggle('selection-mode', enabled);
            bulk.hidden = !enabled;
            if (!enabled) {
              list.querySelectorAll('input[name="request_ids"]').forEach((input) => {
                input.checked = false;
              });
            }
          };

          toggle.addEventListener('click', () => {
            setSelectionMode(!panel.classList.contains('selection-mode'));
          });

          if (cancel) {
            cancel.addEventListener('click', () => setSelectionMode(false));
          }

          selectionForm.addEventListener('submit', () => {
            selectionForm.querySelectorAll('input[type="hidden"][name="request_ids"]').forEach((node) => node.remove());
            list.querySelectorAll('input[name="request_ids"]:checked').forEach((input) => {
              const clone = document.createElement('input');
              clone.type = 'hidden';
              clone.name = 'request_ids';
              clone.value = input.value;
              selectionForm.appendChild(clone);
            });
          });
        });
      })();
    </script>
    """


def document_file_field(file_settings: dict | None = None) -> str:
    file_settings = file_settings or {}
    allowed_extensions = row_value(file_settings, "allowed_extensions") or ""
    max_file_size_mb = row_value(file_settings, "max_file_size_mb", 10)
    return (
        '<div class="document-file-row">'
        '<div class="meeting-file-field document-file-field">'
        '<span>Dosya Ekle</span>'
        '<p class="meeting-file-meta">İsteğe bağlı</p>'
        f'<label class="meeting-file-picker" data-file-picker>'
        f'<span data-file-label>Dosya seç</span>'
        f'<input type="file" name="attachment" accept="{escape(_build_accept_attr(allowed_extensions))}" '
        f'data-file-input data-max-size-mb="{escape(str(max_file_size_mb))}" '
        f'data-allowed-extensions="{escape(allowed_extensions)}" data-default-label="Dosya seç">'
        f'</label>'
        '</div>'
        '</div>'
    )


def quick_document_form(share_users: list | None = None, share_roles: list | None = None, file_settings: dict | None = None) -> str:
    share_users = share_users or []
    share_roles = share_roles or []
    kind_options = {"one_time": "Tekrarsız", "recurring": "Tekrarlı"}
    return f"""
    <div class="task-create-launcher">
      <button class="task-create-button" type="button" data-open-document-create>
        <span class="task-create-icon">+</span>
        <span>Yeni evrak ekle</span>
      </button>
    </div>
    <dialog class="task-create-dialog document-create-dialog" data-document-create-dialog>
      <div class="task-create-dialog-card document-create-dialog-card">
        <div class="panel-header task-create-header">
          <div><h3>Yeni Evrak</h3></div>
          <button class="task-dialog-close" type="button" data-close-document-create aria-label="Kapat">×</button>
        </div>
        <form method="post" action="/documents" enctype="multipart/form-data" class="quick-task-form compact-inline-form document-inline-form document-create-form">
          <div class="quick-doc-grid document-create-grid">
            {input_field("title", "Evrak", required=True, placeholder="Örnek: Aylık denetim dosyası")}
            {select_field("kind", "Tür", kind_options, "one_time", css_class="document-kind-select")}
            <div class="document-frequency-wrap is-hidden">{select_field("frequency", "Periyot", FREQUENCY_LABELS, "monthly")}</div>
            {user_share_field(share_users)}
            {role_share_field(share_roles)}
            {input_field("next_due_date", "Tarih", input_type="date", value=str(date.today()))}
          </div>
          {document_file_field(file_settings)}
          {textarea_field("description", "Kısa Açıklama", "", "Evrakla ilgili kısa not", rows=3, extra_class="compact-note-field")}
          <div class="task-create-actions">
            <button class="mini-link subtle" type="button" data-close-document-create>Vazgeç</button>
            <button class="button" type="submit">Ekle</button>
          </div>
        </form>
      </div>
    </dialog>
    """


def document_form() -> str:
    return quick_document_form()


def edit_document_panel(item, share_users: list | None = None, share_roles: list | None = None, can_manage_directly: bool = True, file_settings: dict | None = None) -> str:
    share_users = share_users or []
    share_roles = share_roles or []
    kind_options = {"one_time": "Tekrarsız", "recurring": "Tekrarlı"}
    frequency_wrap_class = "document-frequency-wrap" + (" is-hidden" if item["kind"] == "one_time" else "")
    share_field_html = user_share_field(share_users, row_value(item, "_share_user_ids", [])) if can_manage_directly else f'<div class="field task-share-readonly"><small class="readonly-tip">Paylaşılan kullanıcı bu alanı değiştiremez. Düzenleme isteği evrak sahibine gider.</small><span>Paylaşım</span><div class="readonly-value">{escape(row_value(item, "_share_summary", "-"))}</div></div>'
    role_field_html = role_share_field(share_roles, row_value(item, "_share_role_ids", [])) if can_manage_directly else f'<div class="field task-share-readonly"><small class="readonly-tip">Rol paylaşımı yalnızca evrak sahibi tarafından değiştirilir.</small><span>Rol</span><div class="readonly-value">{escape(", ".join(row_value(item, "_share_role_names", [])) or "-")}</div></div>'
    submit_label = "Güncelle" if can_manage_directly else "Onay İçin Gönder"
    description_value = row_value(item, "description") or row_value(item, "notes") or ""
    attachment_panel = render_document_attachments(item, can_manage_directly) if row_value(item, "_attachments") is not None else ""
    return f'<div class="documents-edit-bar"><div class="panel-header"><h3>Evrakı Düzenle</h3><a class="text-link" href="/documents">Vazgeç</a></div><form method="post" action="/documents/update" class="quick-task-form compact-inline-form document-inline-form"><input type="hidden" name="id" value="{item["id"]}"><input type="hidden" name="source_kind" value="{item["kind"]}"><div class="quick-doc-grid">{input_field("title", "Evrak", required=True, value=item["title"])}{select_field("kind", "Tür", kind_options, item["kind"], css_class="document-kind-select")}<div class="{frequency_wrap_class}">{select_field("frequency", "Periyot", FREQUENCY_LABELS, item["frequency"] if item["kind"] == "recurring" else "monthly")}</div>{share_field_html}{role_field_html}{input_field("next_due_date", "Tarih", input_type="date", value=row_value(item, "date_raw") or "")}<button class="button" type="submit">{submit_label}</button></div>{textarea_field("description", "Kısa Açıklama", description_value, "Evrakla ilgili kısa not", rows=2, extra_class="compact-note-field")}</form>{attachment_panel}</div>'


def documents_dashboard_page(items: list, quick_form_html: str, edit_item=None) -> bytes:
    return documents_dashboard_page_filtered(items, [], quick_form_html, edit_item, ["all"], {})


def documents_dashboard_page_filtered(active_items: list, completed_items: list, quick_form_html: str, edit_item=None, active_filters: list[str] | None = None, filter_counts: dict | None = None, current_user: dict | None = None, allowed_paths: set[str] | None = None, share_users: list | None = None, share_roles: list | None = None, owner_requests: list | None = None, request_history: list | None = None, edit_can_manage_directly: bool = True, feedback: dict | None = None, file_settings: dict | None = None) -> bytes:
    active_filters = active_filters or []
    filter_counts = filter_counts or {}
    share_users = share_users or []
    share_roles = share_roles or []
    owner_requests = owner_requests or []
    request_history = request_history or []
    feedback = feedback or {}
    feedback_html = ""
    if feedback.get("error"):
        feedback_html = f'<p class="form-error inline-feedback">{escape(feedback["error"])}</p>'
    elif feedback.get("info"):
        feedback_html = f'<p class="form-info inline-feedback">{escape(feedback["info"])}</p>'
    body = f"""
    <section class="documents-shell">
      <div class="documents-toolbar"><div><p class="eyebrow">Evrak</p><h2>Evrak Takibi</h2></div><span class="badge">{len(active_items)} aktif</span></div>
      {feedback_html}
      {quick_form_html}
      {document_request_panel(owner_requests)}
      {document_request_history_panel(request_history)}
      {edit_document_panel(edit_item, share_users, share_roles, edit_can_manage_directly, file_settings) if edit_item else ''}
      <div class="documents-table-wrap task-table-panel task-table-panel-active">{documents_filter_bar(active_filters, filter_counts)}{documents_table_header()}<div class="task-table">{render_documents_table(active_items)}</div></div>
      <div class="documents-table-wrap task-table-panel task-table-panel-completed"><div class="panel-header compact-header"><h3>Tamamlanan Evraklar</h3><span class="badge">{len(completed_items)} kayıt</span></div>{completed_documents_table_header()}<div class="task-table">{render_completed_documents_table(completed_items)}</div></div>
    </section>
    {documents_inline_script()}
    {task_share_script()}
    """
    return layout("Evrak Takibi", body, "/documents", current_user, allowed_paths)


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
    return '<div class="task-header-row document-header-row"><span></span><span>Evrak</span><span>Paylaşım</span><span>Periyot</span><span>Tarih</span><span>Son Tamamlanma</span><span>İşlem</span></div>'


def completed_documents_table_header() -> str:
    return '<div class="task-header-row document-header-row"><span></span><span>Evrak</span><span>Paylaşım</span><span>Periyot</span><span>Son Tarih</span><span>Son Tamamlanma</span><span>İşlem</span></div>'


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
    attachment_count = int(row_value(item, "_attachment_count", 0) or 0)
    attachment_badge = f'<span class="meeting-attachment-badge">{attachment_count} dosya</span>' if attachment_count else ""
    return f'<article class="{row_class}"><form class="task-toggle-form" method="post" action="/documents/toggle"><input type="hidden" name="id" value="{item["id"]}"><input type="hidden" name="kind" value="{item["kind"]}"><input type="hidden" name="next_state" value="{next_state}"><button class="task-check{checked}" type="submit" aria-label="Evrak durumunu değiştir"></button></form><div class="task-main document-main"><div class="task-cell task-cell-title"><h4>{escape(item["title"])}</h4>{attachment_badge}</div>{document_share_cell(item)}<div class="task-cell"><span class="priority-chip medium">{escape(item["frequency_label"])} </span></div><div class="task-cell task-cell-date">{escape(item["date_label"])}</div><div class="task-cell task-cell-date">{escape(item["completed_label"])}</div><div class="task-cell task-cell-actions">{active_document_actions(item)}</div></div></article>'


def render_completed_document_row(item) -> str:
    attachment_count = int(row_value(item, "_attachment_count", 0) or 0)
    attachment_badge = f'<span class="meeting-attachment-badge">{attachment_count} dosya</span>' if attachment_count else ""
    return f'<article class="task-row document-row done"><form class="task-toggle-form" method="post" action="/documents/toggle"><input type="hidden" name="id" value="{item["id"]}"><input type="hidden" name="kind" value="{item["kind"]}"><input type="hidden" name="next_state" value="undone"><button class="task-check checked" type="submit" aria-label="Evrak durumunu değiştir"></button></form><div class="task-main completed-document-main"><div class="task-cell task-cell-title"><h4>{escape(item["title"])}</h4>{attachment_badge}</div>{document_share_cell(item)}<div class="task-cell"><span class="priority-chip medium">{escape(item["frequency_label"])} </span></div><div class="task-cell task-cell-date">{escape(item["date_label"])}</div><div class="task-cell task-cell-date">{escape(item["completed_label"])}</div><div class="task-cell task-cell-actions">{completed_document_actions(item)}</div></div></article>'


def render_document_attachments(item, can_manage_directly: bool = True) -> str:
    attachments = item.get("_attachments", []) if isinstance(item, dict) else []
    file_settings = item.get("_file_settings", {}) if isinstance(item, dict) else {}
    record_id = item["id"] if isinstance(item, dict) else ""
    module_name = "recurring_documents" if row_value(item, "kind") == "recurring" else "documents"
    allowed_extensions = row_value(file_settings, "allowed_extensions") or ""
    max_file_size_mb = row_value(file_settings, "max_file_size_mb", 10)
    upload_hint = (
        f'<p class="meeting-attachment-hint">İzin verilen türler: {escape(allowed_extensions)} • En fazla {escape(str(max_file_size_mb))} MB</p>'
        if allowed_extensions
        else ""
    )
    upload_form = ""
    if can_manage_directly:
        upload_form = (
            f'<form method="post" action="/documents/attachments" enctype="multipart/form-data" class="meeting-attachment-form">'
            f'<input type="hidden" name="document_id" value="{record_id}">'
            f'<input type="hidden" name="kind" value="{module_name}">'
            f'<label class="meeting-file-picker" data-file-picker><span data-file-label>Dosya seç</span><input type="file" name="attachment" required accept="{escape(_build_accept_attr(allowed_extensions))}" data-file-input data-max-size-mb="{escape(str(max_file_size_mb))}" data-allowed-extensions="{escape(allowed_extensions)}" data-default-label="Dosya seç"></label>'
            f'<button class="button secondary" type="submit">Yükle</button>'
            f'</form>'
        )
    if not attachments:
        empty = '<p class="empty-state">Henüz dosya eklenmemiş.</p>'
        return f'<div class="document-attachments-panel">{upload_hint}{upload_form}{empty}</div>'
    rows = []
    for attachment in attachments:
        uploader = row_value(attachment, "uploader_full_name") or row_value(attachment, "uploader_username") or "-"
        delete_form = ""
        if can_manage_directly:
            delete_form = (
                f'<form method="post" action="/attachments/delete" class="inline-form">'
                f'<input type="hidden" name="attachment_id" value="{attachment["id"]}">'
                f'<input type="hidden" name="module_name" value="{module_name}">'
                f'<input type="hidden" name="record_id" value="{record_id}">'
                f'<button class="mini-link danger" type="submit">Sil</button>'
                f'</form>'
            )
        rows.append(
            f'<div class="meeting-attachment-row">'
            f'<div class="meeting-attachment-main"><strong>{escape(row_value(attachment, "original_name") or "Dosya")}</strong><span>{escape(_format_file_size(row_value(attachment, "file_size", 0)))} • {escape(format_datetime(row_value(attachment, "created_at")))} • {escape(uploader)}</span></div>'
            f'<div class="meeting-attachment-actions"><a class="mini-link" href="/attachments/download?id={attachment["id"]}">İndir</a>{delete_form}</div>'
            f'</div>'
        )
    return f'<div class="document-attachments-panel">{upload_hint}{upload_form}<div class="meeting-attachment-list">{"".join(rows)}</div></div>'


def document_share_cell(item) -> str:
    share_count = int(row_value(item, "_share_count", 0) or 0)
    role_count = int(row_value(item, "_share_role_count", 0) or 0)
    share_summary = row_value(item, "_share_summary", "-")
    share_tooltip = row_value(item, "_share_tooltip", "")
    shared_from = row_value(item, "_shared_from", "")
    badge = (
        '<span class="task-share-badge muted">Özel</span>' if share_count == 0 and role_count == 0
        else f'<span class="task-share-badge">{share_count} kişi • {role_count} rol</span>' if share_count and role_count
        else f'<span class="task-share-badge">{share_count} kişi</span>' if share_count
        else f'<span class="task-share-badge">{role_count} rol</span>'
    )
    detail = "Yalnızca size özel" if share_count == 0 and role_count == 0 else share_summary
    origin = f'<span class="task-share-origin">{escape(shared_from)} tarafından paylaşıldı</span>' if shared_from else ""
    return f'<div class="task-cell task-cell-share" title="{escape(share_tooltip)}">{badge}<span class="task-share-text">{escape(detail)}</span>{origin}</div>'


def active_document_actions(item) -> str:
    pending_request_type = row_value(item, "_pending_request_type", "")
    pending_owner = row_value(item, "_pending_request_owner", "")
    if pending_request_type:
        label = "Düzenleme onayı bekliyor" if pending_request_type == "update" else "Silme onayı bekliyor"
        title = f"{label} - {pending_owner}" if pending_owner else label
        short_label = "Düzenleme bekliyor" if pending_request_type == "update" else "Silme bekliyor"
        owner_html = f'<span class="pending-task-owner">{escape(pending_owner)}</span>' if pending_owner else ""
        return f'<div class="row-actions pending-task-action"><span class="pending-task-badge" title="{escape(title)}">{escape(short_label)}</span>{owner_html}</div>'
    return f'<div class="row-actions"><a class="mini-link" href="/documents?edit_kind={item["kind"]}&edit_id={item["id"]}">Düzenle</a><form method="post" action="/documents/delete" class="inline-form"><input type="hidden" name="id" value="{item["id"]}"><input type="hidden" name="kind" value="{item["kind"]}"><button class="mini-link danger" type="submit">Sil</button></form></div>'


def completed_document_actions(item) -> str:
    pending_request_type = row_value(item, "_pending_request_type", "")
    pending_owner = row_value(item, "_pending_request_owner", "")
    if pending_request_type:
        label = "Silme onayı bekliyor"
        title = f"{label} - {pending_owner}" if pending_owner else label
        owner_html = f'<span class="pending-task-owner">{escape(pending_owner)}</span>' if pending_owner else ""
        return f'<div class="row-actions pending-task-action"><span class="pending-task-badge" title="{escape(title)}">Silme bekliyor</span>{owner_html}</div>'
    return (
        f'<div class="row-actions">'
        f'<form method="post" action="/documents/toggle" class="inline-form"><input type="hidden" name="id" value="{item["id"]}"><input type="hidden" name="kind" value="{item["kind"]}"><input type="hidden" name="next_state" value="undone"><button class="mini-link" type="submit">Geri Al</button></form>'
        f'<form method="post" action="/documents/delete" class="inline-form"><input type="hidden" name="id" value="{item["id"]}"><input type="hidden" name="kind" value="{item["kind"]}"><button class="mini-link danger" type="submit">Sil</button></form>'
        f'</div>'
    )


def documents_inline_script() -> str:
    return """
    <script>
      (() => {
        const documentDialog = document.querySelector('[data-document-create-dialog]');
        if (documentDialog) {
          const openButtons = document.querySelectorAll('[data-open-document-create]');
          const closeButtons = documentDialog.querySelectorAll('[data-close-document-create]');
          const openDialog = () => {
            if (typeof documentDialog.showModal === 'function') {
              documentDialog.showModal();
            } else {
              documentDialog.setAttribute('open', 'open');
            }
          };
          const closeDialog = () => {
            if (typeof documentDialog.close === 'function') {
              documentDialog.close();
            } else {
              documentDialog.removeAttribute('open');
            }
          };
          openButtons.forEach((button) => button.addEventListener('click', openDialog));
          closeButtons.forEach((button) => button.addEventListener('click', closeDialog));
          documentDialog.addEventListener('click', (event) => {
            const rect = documentDialog.getBoundingClientRect();
            const inside = (
              event.clientX >= rect.left &&
              event.clientX <= rect.right &&
              event.clientY >= rect.top &&
              event.clientY <= rect.bottom
            );
            if (!inside) closeDialog();
          });
        }
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
        document.querySelectorAll('[data-file-input]').forEach((input) => {
          const picker = input.closest('[data-file-picker]');
          const label = picker?.querySelector('[data-file-label]');
          const defaultLabel = input.dataset.defaultLabel || 'Dosya seç';
          const allowedExtensions = (input.dataset.allowedExtensions || '').split(',').map((item) => item.trim().toLowerCase()).filter(Boolean);
          const maxSizeMb = Number(input.dataset.maxSizeMb || '0');
          const reset = () => {
            if (label) label.textContent = defaultLabel;
            input.value = '';
          };
          input.addEventListener('change', () => {
            const file = input.files && input.files[0];
            if (!file) {
              if (label) label.textContent = defaultLabel;
              return;
            }
            const lowerName = file.name.toLowerCase();
            const extension = lowerName.includes('.') ? `.${lowerName.split('.').pop()}` : '';
            if (allowedExtensions.length && !allowedExtensions.includes(extension)) {
              alert(`Bu dosya türüne izin verilmiyor.\nİzin verilen türler: ${allowedExtensions.join(', ')}`);
              reset();
              return;
            }
            if (maxSizeMb > 0 && file.size > maxSizeMb * 1024 * 1024) {
              alert(`Dosya boyutu sınırı aşıldı.\nEn fazla ${maxSizeMb} MB yükleyebilirsiniz.`);
              reset();
              return;
            }
            if (label) label.textContent = file.name;
          });
        });
      })();
    </script>
    """

def quick_event_form() -> str:
    return f"""
    <div class="task-create-launcher">
      <button class="task-create-button" type="button" data-open-event-create>
        <span class="task-create-icon">+</span>
        <span>Yeni etkinlik ekle</span>
      </button>
    </div>
    <dialog class="task-create-dialog document-create-dialog event-create-dialog" data-event-create-dialog>
      <div class="task-create-dialog-card document-create-dialog-card event-create-dialog-card">
        <div class="panel-header task-create-header">
          <div><h3>Yeni Etkinlik</h3></div>
          <button class="task-dialog-close" type="button" data-close-event-create aria-label="Kapat">×</button>
        </div>
        <form method="post" action="/events" class="quick-task-form compact-inline-form event-inline-form event-create-form">
          <div class="quick-doc-grid event-create-grid">
            {input_field("title", "Etkinlik", required=True, placeholder="Örnek: Bahar Şenliği")}
            {event_level_field([])}
            {input_field("event_date", "Başlangıç", input_type="date", value=str(date.today()))}
            {input_field("end_date", "Bitiş", input_type="date", value=str(date.today()))}
            {input_field("time_range", "Saat aralığı", placeholder="Örnek: 09:00 - 11:30")}
          </div>
          {textarea_field("notes", "Açıklama", "", "Etkinlik detayı, notlar, hazırlanacaklar...")}
          <div class="task-create-actions">
            <button class="mini-link subtle" type="button" data-close-event-create>Vazgeç</button>
            <button class="button" type="submit">Ekle</button>
          </div>
        </form>
      </div>
    </dialog>
    """


def edit_event_panel(item) -> str:
    end_date = row_value(item, "end_date") or row_value(item, "event_date") or ""
    return f'<div class="documents-edit-bar"><div class="panel-header"><h3>Etkinliği Düzenle</h3><a class="text-link" href="/events">Vazgeç</a></div><form method="post" action="/events/update" class="quick-task-form compact-inline-form event-inline-form"><input type="hidden" name="id" value="{item["id"]}"><div class="quick-doc-grid event-form-grid">{input_field("title", "Etkinlik", required=True, value=item["title"])}{event_level_field(_split_event_levels(row_value(item, "level")))}{input_field("event_date", "Başlangıç", input_type="date", value=row_value(item, "event_date") or "")}{input_field("end_date", "Bitiş", input_type="date", value=end_date)}{input_field("time_range", "Saat aralığı", value=row_value(item, "time_range") or "", placeholder="Örnek: 09:00 - 11:30")}</div><div class="event-edit-actions"><button class="button" type="submit">Güncelle</button></div>{textarea_field("notes", "Açıklama", row_value(item, "notes") or "", "Etkinlik detayı, notlar, hazırlanacaklar...")}</form></div>'


def events_page(items: list, quick_form_html: str, active_levels: list[str], level_counts: dict[str, int], active_view: str, month_label: str, calendar_html: str, calendar_nav_html: str, edit_item=None, current_user: dict | None = None, allowed_paths: set[str] | None = None) -> bytes:
    body = f'<section class="documents-shell"><div class="documents-toolbar"><div><p class="eyebrow">Etkinlik</p><h2>Etkinlik Takvimi</h2></div><span class="badge">{len(items)} etkinlik</span></div><div class="documents-compact-form">{quick_form_html}</div>{edit_event_panel(edit_item) if edit_item else ""}<div class="events-layout"><div class="documents-table-wrap"><div class="panel-header compact-header"><h3>Kademe Filtreleri</h3></div>{event_filter_bar(active_levels, level_counts, active_view)}{events_table_header()}<div class="task-table task-table-compact">{render_events_table(items)}</div></div><div class="documents-table-wrap calendar-panel"><div class="panel-header compact-header"><h3>{escape(month_label)}</h3></div>{calendar_view_bar(active_view, active_levels)}{calendar_nav_html}{calendar_html}</div></div></section>{event_detail_dialog_markup()}{calendar_day_dialog_markup()}{event_form_script()}'
    return layout("Etkinlik Takvimi", body, "/events", current_user, allowed_paths)


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


def calendar_nav_bar(prev_href: str, next_href: str, today_href: str = "/events") -> str:
    return (
        f'<div class="calendar-nav">'
        f'<a class="mini-link" href="{escape(prev_href)}">Önceki</a>'
        f'<a class="mini-link subtle" href="{escape(today_href)}">Bugün</a>'
        f'<a class="mini-link" href="{escape(next_href)}">Sonraki</a>'
        f'</div>'
    )


def render_event_calendar(year: int, month: int, date_map: dict[str, list[dict]]) -> tuple[str, str]:
    label = f"{MONTH_NAMES[month - 1]} {year}"
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdatescalendar(year, month)
    today = date.today()
    cells = []
    palette = ["tone-a", "tone-b", "tone-c", "tone-d"]
    for week in weeks:
        for day_obj in week:
            key = day_obj.strftime("%Y-%m-%d")
            events = date_map.get(key, [])
            muted = " muted" if day_obj.month != month else ""
            today_class = " today" if day_obj == today else ""
            holiday_day_class = " holiday-day" if any(bool(event.get("is_holiday")) for event in events) else ""
            items = []
            for index, event in enumerate(events[:4]):
                is_holiday = bool(event.get("is_holiday"))
                tone = "tone-holiday" if is_holiday else palette[index % len(palette)]
                title = escape(event.get("title", "Etkinlik"))
                level = escape(event.get("level_label", ""))
                tooltip = title if not level or level == "Belirtilmedi" else f"{title} - {level}"
                level_html = (
                    f'<span class="calendar-event-level">{level}</span>'
                    if level and level != "Belirtilmedi"
                    else ""
                )
                items.append(
                    f'<div class="calendar-event-pill {tone}" title="{tooltip}">'
                    f'<span class="calendar-event-dot" aria-hidden="true"></span>'
                    f'<span class="calendar-event-copy">'
                    f'<span class="calendar-event-title">{title}</span>'
                    f'{level_html}'
                    f'</span>'
                    f'</div>'
                )
            extra = ""
            if len(events) > 4:
                extra = f'<div class="calendar-more">+{len(events) - 4} etkinlik</div>'
            day_events_payload = json.dumps(
                [
                    {
                        "title": event.get("title", "Etkinlik"),
                        "level_label": event.get("level_label", "Belirtilmedi"),
                        "time_range": event.get("time_range", ""),
                        "notes": event.get("notes", ""),
                        "is_holiday": bool(event.get("is_holiday")),
                    }
                    for event in events
                ],
                ensure_ascii=False,
            ).replace("</", "<\\/")
            cells.append(
                f'<div class="calendar-cell{muted}{today_class}{holiday_day_class}">'
                f'<div class="calendar-day-head"><button type="button" class="calendar-day-open" data-calendar-open data-calendar-day="{key}" aria-label="{key} gününü aç"><strong>{day_obj.day}</strong></button></div>'
                f'<div class="calendar-events">{"".join(items)}{extra}</div>'
                f'<script type="application/json" data-day-events>{day_events_payload}</script>'
                f'</div>'
            )
    html = (
        '<div class="calendar-grid calendar-weekdays">'
        + "".join(f'<span>{name}</span>' for name in WEEKDAY_NAMES)
        + '</div><div class="calendar-grid calendar-grid-month">'
        + "".join(cells)
        + "</div>"
    )
    return label, html


def render_event_year_calendar(year: int, date_map: dict[str, list[dict]], active_levels: list[str]) -> tuple[str, str]:
    cards = []
    level_suffix = "".join(f"&level={level}" for level in active_levels)
    for month in range(1, 13):
        count = sum(len(entries) for key, entries in date_map.items() if key.startswith(f"{year:04d}-{month:02d}-"))
        href = f"/events?month={year:04d}-{month:02d}{level_suffix}"
        cards.append(f'<a class="year-calendar-card" href="{href}"><strong>{MONTH_NAMES[month - 1]}</strong><span>{count} etkinlik</span></a>')
    return str(year), '<div class="year-calendar-grid">' + "".join(cards) + '</div>'


def events_table_header() -> str:
    return '<div class="task-header-row event-header-row"><span>Etkinlik</span><span>Kademe</span><span>Tarih/Saat</span><span>İşlem</span></div>'


def render_events_table(items: list) -> str:
    if not items:
        return '<p class="empty-state">Henüz etkinlik kaydı yok.</p>'
    return "".join(render_event_row(item) for item in items)


def render_event_row(item) -> str:
    title = escape(row_value(item, "title") or "Etkinlik")
    levels = render_event_level_badges(row_value(item, "level", ""))
    date_label = escape(format_date_range(row_value(item, "event_date"), row_value(item, "end_date")))
    time_range = escape(row_value(item, "time_range") or "-")
    notes = row_value(item, "notes") or ""
    notes_short = escape((notes[:88] + "...") if len(notes) > 88 else notes) if notes else ""
    notes_full = escape(notes or "-")
    return (
        f'<article class="task-row document-row event-row">'
        f'<div class="task-main event-main">'
        f'<div class="task-cell task-cell-title">'
        f'<button class="event-title-link" type="button" data-event-open '
        f'data-event-title="{title}" '
        f'data-event-level="{escape(format_event_levels(row_value(item, "level")))}" '
        f'data-event-date="{date_label}" '
        f'data-event-time="{time_range}" '
        f'data-event-notes="{notes_full}">{title}</button>'
        f'{f"<small>{notes_short}</small>" if notes_short else ""}'
        f'</div>'
        f'<div class="task-cell">{levels}</div>'
        f'<div class="task-cell task-cell-date"><span>{date_label}</span><small>{time_range}</small></div>'
        f'<div class="task-cell task-cell-actions"><div class="row-actions event-row-actions">'
        f'<a class="mini-link icon-link" href="/events?edit={item["id"]}" title="Düzenle" aria-label="Düzenle">&#9998;</a>'
        f'<form method="post" action="/events/delete" class="inline-form">'
        f'<input type="hidden" name="id" value="{item["id"]}">'
        f'<button class="mini-link danger icon-link" type="submit" title="Sil" aria-label="Sil">&#128465;</button>'
        f'</form></div></div></div></article>'
    )


def event_detail_dialog_markup() -> str:
    return """
    <dialog class="task-create-dialog event-detail-dialog" data-event-detail-dialog>
      <div class="task-create-dialog-card event-detail-card">
        <div class="panel-header task-create-header">
          <div><h3 data-event-detail-title>Etkinlik Detayı</h3></div>
          <button class="task-dialog-close" type="button" data-event-detail-close aria-label="Kapat">×</button>
        </div>
        <div class="event-detail-grid">
          <div><span>Tarih</span><strong data-event-detail-date>-</strong></div>
          <div><span>Saat aralığı</span><strong data-event-detail-time>-</strong></div>
          <div><span>Kademe</span><strong data-event-detail-level>-</strong></div>
          <div class="event-detail-notes"><span>Açıklama</span><p data-event-detail-notes>-</p></div>
        </div>
      </div>
    </dialog>
    """


def calendar_day_dialog_markup() -> str:
    return """
    <dialog class="task-create-dialog event-detail-dialog calendar-day-dialog" data-calendar-day-dialog>
      <div class="task-create-dialog-card event-detail-card calendar-day-card">
        <div class="panel-header task-create-header">
          <div><h3 data-calendar-day-title>Gün Etkinlikleri</h3></div>
          <button class="task-dialog-close" type="button" data-calendar-day-close aria-label="Kapat">×</button>
        </div>
        <div class="calendar-day-list" data-calendar-day-list></div>
      </div>
    </dialog>
    """


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
        if (window.__pelixiEventFormInit) return;
        window.__pelixiEventFormInit = true;

        const eventDialog = document.querySelector('[data-event-create-dialog]');
        if (eventDialog) {
          const openButtons = document.querySelectorAll('[data-open-event-create]');
          const closeButtons = eventDialog.querySelectorAll('[data-close-event-create]');
          const openDialog = () => {
            if (typeof eventDialog.showModal === 'function') {
              eventDialog.showModal();
            } else {
              eventDialog.setAttribute('open', 'open');
            }
          };
          const closeDialog = () => {
            if (typeof eventDialog.close === 'function') {
              eventDialog.close();
            } else {
              eventDialog.removeAttribute('open');
            }
          };
          openButtons.forEach((button) => button.addEventListener('click', openDialog));
          closeButtons.forEach((button) => button.addEventListener('click', closeDialog));
          eventDialog.addEventListener('click', (event) => {
            const rect = eventDialog.getBoundingClientRect();
            const inside = (
              event.clientX >= rect.left &&
              event.clientX <= rect.right &&
              event.clientY >= rect.top &&
              event.clientY <= rect.bottom
            );
            if (!inside) closeDialog();
          });
        }
        const eventForms = [...document.querySelectorAll('.event-inline-form')];
        const levelDropdowns = [...document.querySelectorAll('.event-inline-form [data-event-level-dropdown]')];
        const closeLevelDropdowns = (exceptNode = null) => {
          levelDropdowns.forEach((details) => {
            if (exceptNode && details === exceptNode) return;
            details.removeAttribute('open');
          });
        };
        const updateDropdown = (details) => {
          const summary = details.querySelector('[data-event-level-summary]');
          const checked = [...details.querySelectorAll('input[type="checkbox"]:checked')].map((node) => node.value);
          details.querySelectorAll('.event-level-chip').forEach((chip) => {
            const input = chip.querySelector('input[type="checkbox"]');
            chip.classList.toggle('active', !!input?.checked);
          });
          if (summary) summary.textContent = checked.length ? checked.join(', ') : 'Kademe seçin';
        };
        levelDropdowns.forEach((details) => {
          updateDropdown(details);
          details.addEventListener('change', () => updateDropdown(details));
          details.addEventListener('toggle', () => {
            if (!details.open) return;
            closeLevelDropdowns(details);
          });
        });
        eventForms.forEach((form) => {
          form.addEventListener('pointerdown', (event) => {
            const target = event.target;
            if (!(target instanceof Element)) return;
            const activeDetails = levelDropdowns.find((details) => details.contains(target));
            closeLevelDropdowns(activeDetails || null);
          });
          form.addEventListener('focusin', (event) => {
            const target = event.target;
            if (!(target instanceof Element)) return;
            const activeDetails = levelDropdowns.find((details) => details.contains(target));
            closeLevelDropdowns(activeDetails || null);
          });
        });
        document.addEventListener('keydown', (event) => {
          if (event.key === 'Escape') {
            closeLevelDropdowns();
          }
        });

        const syncEventDates = (form) => {
          const startInput = form.querySelector('input[name="event_date"]');
          const endInput = form.querySelector('input[name="end_date"]');
          if (!startInput || !endInput) return;

          const applyLimits = () => {
            if (startInput.value) {
              endInput.min = startInput.value;
              if (!endInput.value || endInput.value < startInput.value) {
                endInput.value = startInput.value;
              }
            } else {
              endInput.min = "";
            }
          };

          startInput.addEventListener('change', applyLimits);
          endInput.addEventListener('change', () => {
            if (startInput.value && endInput.value && endInput.value < startInput.value) {
              endInput.value = startInput.value;
            }
          });

          applyLimits();
        };

        document.querySelectorAll('.event-inline-form').forEach(syncEventDates);

        const detailDialog = document.querySelector('[data-event-detail-dialog]');
        if (detailDialog) {
          const closeButtons = detailDialog.querySelectorAll('[data-event-detail-close]');
          const titleNode = detailDialog.querySelector('[data-event-detail-title]');
          const dateNode = detailDialog.querySelector('[data-event-detail-date]');
          const timeNode = detailDialog.querySelector('[data-event-detail-time]');
          const levelNode = detailDialog.querySelector('[data-event-detail-level]');
          const notesNode = detailDialog.querySelector('[data-event-detail-notes]');

          const closeDetail = () => {
            if (typeof detailDialog.close === 'function') {
              detailDialog.close();
            } else {
              detailDialog.removeAttribute('open');
            }
          };
          const openDetail = () => {
            if (typeof detailDialog.showModal === 'function') {
              detailDialog.showModal();
            } else {
              detailDialog.setAttribute('open', 'open');
            }
          };

          document.querySelectorAll('[data-event-open]').forEach((button) => {
            button.addEventListener('click', () => {
              if (titleNode) titleNode.textContent = button.dataset.eventTitle || 'Etkinlik Detayı';
              if (dateNode) dateNode.textContent = button.dataset.eventDate || '-';
              if (timeNode) timeNode.textContent = button.dataset.eventTime || '-';
              if (levelNode) levelNode.textContent = button.dataset.eventLevel || '-';
              if (notesNode) notesNode.textContent = button.dataset.eventNotes || '-';
              openDetail();
            });
          });

          closeButtons.forEach((button) => button.addEventListener('click', closeDetail));
          detailDialog.addEventListener('click', (event) => {
            const rect = detailDialog.getBoundingClientRect();
            const inside = (
              event.clientX >= rect.left &&
              event.clientX <= rect.right &&
              event.clientY >= rect.top &&
              event.clientY <= rect.bottom
            );
            if (!inside) closeDetail();
          });
        }

        const dayDialog = document.querySelector('[data-calendar-day-dialog]');
        if (dayDialog) {
          const titleNode = dayDialog.querySelector('[data-calendar-day-title]');
          const listNode = dayDialog.querySelector('[data-calendar-day-list]');
          const closeButtons = dayDialog.querySelectorAll('[data-calendar-day-close]');

          const closeDayDialog = () => {
            if (typeof dayDialog.close === 'function') {
              dayDialog.close();
            } else {
              dayDialog.removeAttribute('open');
            }
          };
          const openDayDialog = () => {
            if (typeof dayDialog.showModal === 'function') {
              dayDialog.showModal();
            } else {
              dayDialog.setAttribute('open', 'open');
            }
          };
          const escapeHtml = (value) => {
            const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
            return String(value || '').replace(/[&<>"']/g, (m) => map[m]);
          };

          document.querySelectorAll('[data-calendar-open]').forEach((button) => {
            button.addEventListener('click', () => {
              const cell = button.closest('.calendar-cell');
              const payloadNode = cell?.querySelector('[data-day-events]');
              const day = button.dataset.calendarDay || '';
              let events = [];
              if (payloadNode?.textContent) {
                try {
                  events = JSON.parse(payloadNode.textContent);
                } catch (_) {
                  events = [];
                }
              }
              if (titleNode) titleNode.textContent = day ? `${day} etkinlikleri` : 'Gün Etkinlikleri';
              if (listNode) {
                if (!events.length) {
                  listNode.innerHTML = '<p class="empty-state">Bu gün için etkinlik yok.</p>';
                } else {
                  listNode.innerHTML = events.map((event) => {
                    const holidayClass = event.is_holiday ? ' holiday' : '';
                    const title = escapeHtml(event.title || 'Etkinlik');
                    const level = escapeHtml(event.level_label || 'Belirtilmedi');
                    const time = escapeHtml(event.time_range || '-');
                    const notes = escapeHtml(event.notes || '-');
                    return `<article class="calendar-day-item${holidayClass}"><h4>${title}</h4><p><strong>Kademe:</strong> ${level}</p><p><strong>Saat:</strong> ${time}</p><p><strong>Açıklama:</strong> ${notes}</p></article>`;
                  }).join('');
                }
              }
              openDayDialog();
            });
          });

          closeButtons.forEach((button) => button.addEventListener('click', closeDayDialog));
          dayDialog.addEventListener('click', (event) => {
            const rect = dayDialog.getBoundingClientRect();
            const inside = (
              event.clientX >= rect.left &&
              event.clientX <= rect.right &&
              event.clientY >= rect.top &&
              event.clientY <= rect.bottom
            );
            if (!inside) closeDayDialog();
          });
        }
      })();
    </script>
    """

def quick_supplier_form_v3() -> str:
    return f"""
    <div class="task-create-launcher">
      <button class="task-create-button" type="button" data-open-supplier-create>
        <span class="task-create-icon">+</span>
        <span>Yeni tedarikçi ekle</span>
      </button>
    </div>
    <dialog class="task-create-dialog supplier-create-dialog" data-supplier-create-dialog>
      <div class="task-create-dialog-card supplier-create-dialog-card">
        <div class="panel-header task-create-header">
          <div><h3>Yeni Tedarikçi</h3></div>
          <button class="task-dialog-close" type="button" data-close-supplier-create aria-label="Kapat">×</button>
        </div>
        <form method="post" action="/suppliers" class="quick-task-form supplier-create-form">
          <div class="quick-supplier-grid supplier-create-grid">
        {input_field("company_name", "Firma", required=True, placeholder="Örnek: Mavi Matbaa")}
        {input_field("contact_name", "Yetkili", placeholder="Örnek: Ayşe Demir")}
        {input_field("phone", "Telefon", placeholder="Örnek: 5551234567", extra_attrs='inputmode="numeric" maxlength="10" pattern="[0-9]{10}" oninput="this.value=this.value.replace(/\\D/g, \"\").slice(0,10)"')}
        {input_field("service_type", "Hizmet", placeholder="Örnek: Baskı / Servis / Yemek")}
          </div>
          <div class="task-create-actions">
            <button class="mini-link subtle" type="button" data-close-supplier-create>Vazgeç</button>
            <button class="button" type="submit">Ekle</button>
          </div>
        </form>
      </div>
    </dialog>
    """


def suppliers_page(items: list, selected_supplier, notes: list, edit_item=None, note_edit=None, show_note_form: bool = False, current_user: dict | None = None, allowed_paths: set[str] | None = None) -> bytes:
    selected_name = selected_supplier["company_name"] if selected_supplier else "Tedarikçi seçin"
    body = f'<section class="documents-shell"><div class="documents-toolbar"><div><p class="eyebrow">Tedarikçi</p><h2>Tedarikçiler</h2></div><span class="badge">{len(items)} kayıt</span></div>{quick_supplier_form_v3()}{edit_supplier_panel(edit_item) if edit_item else ""}<div class="documents-table-wrap task-table-panel task-table-panel-completed"><div class="panel-header compact-header"><h3>Tedarikçi Listesi</h3></div>{suppliers_table_header()}<div class="task-table">{render_suppliers_table(items, selected_supplier["id"] if selected_supplier else None)}</div></div><div class="documents-table-wrap supplier-notes-panel"><div class="panel-header compact-header"><h3>{escape(selected_name)} Görüşme Notları</h3></div>{supplier_note_form(selected_supplier, note_edit) if (show_note_form or note_edit) else ""}<div class="supplier-note-list">{render_supplier_notes(notes, selected_supplier)}</div></div></section>{supplier_form_script()}'
    return layout("Tedarikçiler", body, "/suppliers", current_user, allowed_paths)


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


def supplier_form_script() -> str:
    return """
    <script>
      (() => {
        const supplierDialog = document.querySelector('[data-supplier-create-dialog]');
        if (!supplierDialog) return;
        const openButtons = document.querySelectorAll('[data-open-supplier-create]');
        const closeButtons = supplierDialog.querySelectorAll('[data-close-supplier-create]');
        const openDialog = () => {
          if (typeof supplierDialog.showModal === 'function') {
            supplierDialog.showModal();
          } else {
            supplierDialog.setAttribute('open', 'open');
          }
        };
        const closeDialog = () => {
          if (typeof supplierDialog.close === 'function') {
            supplierDialog.close();
          } else {
            supplierDialog.removeAttribute('open');
          }
        };
        openButtons.forEach((button) => button.addEventListener('click', openDialog));
        closeButtons.forEach((button) => button.addEventListener('click', closeDialog));
        supplierDialog.addEventListener('click', (event) => {
          const rect = supplierDialog.getBoundingClientRect();
          const inside = (
            event.clientX >= rect.left &&
            event.clientX <= rect.right &&
            event.clientY >= rect.top &&
            event.clientY <= rect.bottom
          );
          if (!inside) closeDialog();
        });
      })();
    </script>
    """


def meetings_workspace_page_v3(items: list, selected_item=None, templates: list | None = None, active_tab: str = "notes", edit_item=None, show_new: bool = False, current_user: dict | None = None, allowed_paths: set[str] | None = None, feedback: dict | None = None, file_settings: dict | None = None) -> bytes:
    templates = templates or []
    feedback = feedback or {}
    file_settings = file_settings or {}
    feedback_html = ""
    if feedback.get("error"):
        feedback_html = f'<p class="form-error inline-feedback">{escape(feedback["error"])}</p>'
    elif feedback.get("info"):
        feedback_html = f'<p class="form-info inline-feedback">{escape(feedback["info"])}</p>'
    if show_new:
        content = f'<div class="meeting-action-bar"><div class="meeting-action-group"><a class="mini-link" href="/meetings">Listeye Dön</a></div></div><div class="documents-compact-form meeting-form-panel"><div class="panel-header compact-header"><h3>Yeni Toplantı</h3></div><form method="post" action="/meetings" enctype="multipart/form-data" class="quick-task-form compact-inline-form meeting-editor" data-meeting-editor>{meeting_quick_form_v3(templates, file_settings)}</form></div>'
    elif edit_item:
        content = f'<div class="meeting-action-bar"><div class="meeting-action-group"><a class="mini-link" href="/meetings?meeting={edit_item["id"]}">Detaya Dön</a><a class="mini-link" href="/meetings">Listeye Dön</a></div></div>{edit_meeting_panel_v3(edit_item, templates)}'
    elif selected_item:
        content = f'<div class="meeting-action-bar"><div class="meeting-action-group"><a class="mini-link" href="/meetings">Listeye Dön</a><a class="mini-link" href="/meetings?meeting={selected_item["id"]}&edit={selected_item["id"]}">Düzenle</a><form method="post" action="/meetings/delete" class="inline-form"><input type="hidden" name="id" value="{selected_item["id"]}"><button class="mini-link danger" type="submit">Sil</button></form></div></div><div class="documents-table-wrap task-table-panel task-table-panel-completed meeting-detail-page"><div class="panel-header compact-header"><h3>{escape(selected_item["title"])}</h3><span class="badge">{escape(format_date(selected_item["meeting_date"]))}</span></div>{render_meeting_detail_v3(selected_item)}</div>'
    else:
        content = f'<div class="task-create-launcher"><a class="task-create-button" href="/meetings?new=1"><span class="task-create-icon">+</span><span>Yeni toplantı ekle</span></a></div><div class="documents-table-wrap task-table-panel task-table-panel-active"><div class="panel-header compact-header"><h3>Toplantı Listesi</h3><span class="badge">{len(items)} kayıt</span></div>{meetings_table_header_v3()}<div class="task-table">{render_meetings_table_v3(items, None)}</div></div>'
    body = f'<section class="documents-shell meetings-shell"><div class="documents-toolbar"><div><p class="eyebrow">Toplantı</p><h2>Toplantı Notları</h2></div><span class="badge">{len(items)} kayıt</span></div>{feedback_html}{content}</section>{meeting_form_script_v3()}'
    return layout("Toplantı Notları", body, "/meetings", current_user, allowed_paths)


def meeting_settings_panel_v3(templates: list) -> str:
    rows = []
    for item in templates:
        rows.append(f'<article class="task-row meeting-template-row"><div class="task-main meeting-template-main"><div class="task-cell task-cell-title"><h4>{escape(item["title"])}</h4></div><div class="task-cell task-cell-actions"><div class="row-actions"><form method="post" action="/meeting-templates/delete" class="inline-form"><input type="hidden" name="id" value="{item["id"]}"><button class="mini-link danger" type="submit">Sil</button></form></div></div></div></article>')
    inner = "".join(rows) if rows else '<p class="empty-state">Henüz başlık eklenmemiş.</p>'
    return f'<div class="documents-table-wrap"><div class="panel-header compact-header"><h3>Başlık Seçenekleri</h3></div><form method="post" action="/meeting-templates" class="quick-task-form compact-inline-form"><div class="meeting-template-grid">{input_field("title", "Yeni Başlık", required=True, placeholder="Örnek: Zümre toplantısı")}<button class="button" type="submit">Ekle</button></div></form><div class="task-table meeting-template-list">{inner}</div></div>'


def meeting_templates_page(templates: list, current_user: dict | None = None, allowed_paths: set[str] | None = None, feedback: dict | None = None) -> bytes:
    feedback = feedback or {}
    feedback_html = ""
    if feedback.get("error"):
        feedback_html = f'<p class="form-error inline-feedback">{escape(feedback["error"])}</p>'
    elif feedback.get("info"):
        feedback_html = f'<p class="form-info inline-feedback">{escape(feedback["info"])}</p>'
    body = f'<section class="documents-shell meetings-shell"><div class="documents-toolbar"><div><p class="eyebrow">Ayarlar</p><h2>Başlık Ayarları</h2></div><span class="badge">{len(templates)} başlık</span></div>{feedback_html}{meeting_settings_panel_v3(templates)}</section>'
    return layout("Başlık Ayarları", body, "/meeting-templates", current_user, allowed_paths)


def meeting_quick_form_v3(templates: list, file_settings: dict | None = None) -> str:
    file_settings = file_settings or {}
    allowed_extensions = row_value(file_settings, "allowed_extensions") or ""
    max_file_size_mb = row_value(file_settings, "max_file_size_mb", 10)
    accept_attr = _build_accept_attr(allowed_extensions)
    file_field = (
        '<div class="meeting-file-field">'
        '<span>Dosya Ekle</span>'
        '<p class="meeting-file-meta">İsteğe bağlı</p>'
        f'<label class="meeting-file-picker meeting-file-picker-inline" data-file-picker>'
        f'<span data-file-label>Dosya seç</span>'
        f'<input type="file" name="attachment" accept="{escape(accept_attr)}" data-file-input data-max-size-mb="{escape(str(max_file_size_mb))}" data-allowed-extensions="{escape(allowed_extensions)}" data-default-label="Dosya seç">'
        f'</label>'
        '</div>'
    )
    return f'<div class="meeting-create-top-grid">{meeting_title_field_v3(templates)}{file_field}{input_field("meeting_date", "Tarih", input_type="date", value=str(date.today()), required=True)}<div class="meeting-create-submit"><button class="button" type="submit">Kaydet</button></div></div>{meeting_line_editor_v3("Gündem", "agenda_item", ["Madde 1", "Madde 2"])}{meeting_line_editor_v3("Kararlar", "decision_item", ["Karar 1"])}{textarea_field("notes", "Notlar")}'


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
    attachment_count = int(row_value(item, "_attachment_count", 0) or 0)
    attachment_badge = f'<span class="meeting-attachment-badge">{attachment_count} dosya</span>' if attachment_count else ""
    return f'<article class="{row_class}"><div class="task-main meeting-main"><div class="task-cell task-cell-title"><h4><a class="supplier-link" href="/meetings?meeting={item["id"]}">{escape(item["title"])}</a></h4>{attachment_badge}</div><div class="task-cell task-cell-date">{escape(format_date(row_value(item, "meeting_date")))}</div><div class="task-cell meeting-preview">{escape(preview)}</div><div class="task-cell task-cell-actions"><div class="row-actions"><a class="mini-link" href="/meetings?meeting={item["id"]}&edit={item["id"]}">Düzenle</a><form method="post" action="/meetings/delete" class="inline-form"><input type="hidden" name="id" value="{item["id"]}"><button class="mini-link danger" type="submit">Sil</button></form></div></div></div></article>'


def render_meeting_detail_v3(item) -> str:
    if not item:
        return '<p class="empty-state">Detayı görmek için listeden bir toplantı seçin.</p>'
    return f'<div class="meeting-detail-grid">{meeting_detail_section("Gündem", render_numbered_list_v2(row_value(item, "agenda")))}{meeting_detail_section("Kararlar", render_decision_list_v3(item))}{meeting_detail_section("Notlar", render_notes_text_v2(row_value(item, "notes")))}{meeting_detail_section("Dosyalar", render_meeting_attachments(item))}</div>'


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


def render_meeting_attachments(item) -> str:
    attachments = item.get("_attachments", []) if isinstance(item, dict) else []
    file_settings = item.get("_file_settings", {}) if isinstance(item, dict) else {}
    meeting_id = item["id"] if isinstance(item, dict) else ""
    allowed_extensions = row_value(file_settings, "allowed_extensions") or ""
    max_file_size_mb = row_value(file_settings, "max_file_size_mb", 10)
    upload_hint = (
        f'<p class="meeting-attachment-hint">İzin verilen türler: {escape(allowed_extensions)} • En fazla {escape(str(max_file_size_mb))} MB</p>'
        if allowed_extensions
        else ""
    )
    upload_form = (
        f'<form method="post" action="/meetings/attachments" enctype="multipart/form-data" class="meeting-attachment-form">'
        f'<input type="hidden" name="meeting_id" value="{meeting_id}">'
        f'<label class="meeting-file-picker" data-file-picker><span data-file-label>Dosya seç</span><input type="file" name="attachment" required accept="{escape(_build_accept_attr(allowed_extensions))}" data-file-input data-max-size-mb="{escape(str(max_file_size_mb))}" data-allowed-extensions="{escape(allowed_extensions)}" data-default-label="Dosya seç"></label>'
        f'<button class="button secondary" type="submit">Yükle</button>'
        f'</form>'
    )
    if not attachments:
        return upload_hint + upload_form + '<p class="empty-state">Henüz dosya eklenmemiş.</p>'
    rows = []
    for attachment in attachments:
        uploader = row_value(attachment, "uploader_full_name") or row_value(attachment, "uploader_username") or "-"
        rows.append(
            f'<div class="meeting-attachment-row">'
            f'<div class="meeting-attachment-main"><strong>{escape(row_value(attachment, "original_name") or "Dosya")}</strong><span>{escape(_format_file_size(row_value(attachment, "file_size", 0)))} • {escape(format_datetime(row_value(attachment, "created_at")))} • {escape(uploader)}</span></div>'
            f'<div class="meeting-attachment-actions"><a class="mini-link" href="/attachments/download?id={attachment["id"]}">İndir</a><form method="post" action="/attachments/delete" class="inline-form"><input type="hidden" name="attachment_id" value="{attachment["id"]}"><input type="hidden" name="module_name" value="meetings"><input type="hidden" name="record_id" value="{meeting_id}"><button class="mini-link danger" type="submit">Sil</button></form></div>'
            f'</div>'
        )
    return upload_hint + upload_form + f'<div class="meeting-attachment-list">{"".join(rows)}</div>'


def _format_file_size(value) -> str:
    try:
        size = int(value or 0)
    except (TypeError, ValueError):
        return "-"
    units = ["B", "KB", "MB", "GB"]
    unit_index = 0
    amount = float(size)
    while amount >= 1024 and unit_index < len(units) - 1:
        amount /= 1024
        unit_index += 1
    return f"{amount:.0f} {units[unit_index]}" if unit_index == 0 else f"{amount:.1f} {units[unit_index]}"


def _build_accept_attr(raw_value: str) -> str:
    values = []
    for part in (raw_value or "").split(","):
        cleaned = part.strip().lower()
        if not cleaned:
            continue
        if not cleaned.startswith("."):
            cleaned = f".{cleaned}"
        if cleaned not in values:
            values.append(cleaned)
    return ",".join(values)


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
        document.querySelectorAll('[data-file-input]').forEach((input) => {{
          const picker = input.closest('[data-file-picker]');
          const label = picker?.querySelector('[data-file-label]');
          const defaultLabel = input.dataset.defaultLabel || 'Dosya seç';
          const allowedExtensions = (input.dataset.allowedExtensions || '').split(',').map((item) => item.trim().toLowerCase()).filter(Boolean);
          const maxSizeMb = Number(input.dataset.maxSizeMb || '0');
          const reset = () => {{
            if (label) label.textContent = defaultLabel;
            input.value = '';
          }};
          input.addEventListener('change', () => {{
            const file = input.files && input.files[0];
            if (!file) {{
              if (label) label.textContent = defaultLabel;
              return;
            }}
            const lowerName = file.name.toLowerCase();
            const extension = lowerName.includes('.') ? `.${{lowerName.split('.').pop()}}` : '';
            if (allowedExtensions.length && !allowedExtensions.includes(extension)) {{
              alert(`Bu dosya türüne izin verilmiyor.\\nİzin verilen türler: ${{allowedExtensions.join(', ')}}`);
              reset();
              return;
            }}
            if (maxSizeMb > 0 && file.size > maxSizeMb * 1024 * 1024) {{
              alert(`Dosya boyutu sınırı aşıldı.\\nEn fazla ${{maxSizeMb}} MB yükleyebilirsiniz.`);
              reset();
              return;
            }}
            if (label) label.textContent = file.name;
          }});
        }});
      }})();
    </script>
    """


def render_task_item(item) -> str:
    status_label = translate_label(item["status"], TASK_STATUS_LABELS)
    priority_label = translate_label(item["priority"], PRIORITY_LABELS)
    responsible = row_value(item, "responsible_person") or "Sorumlu belirtilmedi"
    share_summary = row_value(item, "_share_summary") or "-"
    shared_from = row_value(item, "_shared_from") or ""
    shared_from_html = f'<span>Gönderen: {escape(shared_from)}</span>' if shared_from else ""
    description = (row_value(item, "description") or "").strip()
    description_html = f'<p>{escape(description)}</p>' if description else ""
    return f'<article class="record-card"><div class="record-top"><h4>{escape(item["title"])}</h4><span class="status-pill {escape(item["status"])}">{escape(status_label)}</span></div>{description_html}<div class="meta-row"><span>{escape(responsible)}</span><span>Paylaşım: {escape(share_summary)}</span>{shared_from_html}<span>Öncelik: {escape(priority_label)}</span><span>Termin: {escape(row_value(item, "due_date", "-"))}</span></div></article>'


def render_document_item(item) -> str:
    item_kind = row_value(item, "kind", "one_time")
    status_value = row_value(item, "status")
    if item_kind == "recurring":
        status_value = "waiting"
    status_css = status_value or "waiting"
    status_label = translate_label(status_css, DOCUMENT_STATUS_LABELS)
    description = (row_value(item, "description") or row_value(item, "notes") or "").strip()
    description_html = f'<p>{escape(description)}</p>' if description else ""
    meta_left = row_value(item, "institution") or row_value(item, "frequency_label") or "Kurum belirtilmedi"
    due_value = row_value(item, "due_date") or row_value(item, "date_label") or "-"
    return f'<article class="record-card"><div class="record-top"><h4>{escape(item["title"])}</h4><span class="status-pill {escape(status_css)}">{escape(status_label)}</span></div>{description_html}<div class="meta-row"><span>{escape(meta_left)}</span><span>Termin: {escape(due_value)}</span></div></article>'


def render_supplier_item(item) -> str:
    return f'<article class="record-card"><div class="record-top"><h4>{escape(item["company_name"])}</h4><span class="status-pill neutral">{escape(row_value(item, "service_type") or "Tedarikçi")}</span></div><p>{escape(row_value(item, "notes") or "Not eklenmemiş.")}</p><div class="meta-row"><span>{escape(row_value(item, "contact_name", "Yetkili belirtilmedi"))}</span><span>{escape(row_value(item, "phone", "-"))}</span></div></article>'


def render_meeting_item(item) -> str:
    return f'<article class="record-card"><div class="record-top"><h4>{escape(item["title"])}</h4><span class="status-pill neutral">{escape(format_date(row_value(item, "meeting_date")))}</span></div><p>{escape(row_value(item, "agenda") or "Gündem yazılmamış.")}</p><div class="meta-row"><span>{escape(row_value(item, "meeting_type", "Genel"))}</span><span>{escape(row_value(item, "participants") or "Katılımcı belirtilmedi")}</span></div></article>'


def render_event_card(item) -> str:
    return f'<article class="record-card"><div class="record-top"><h4>{escape(item["title"])}</h4><span class="status-pill neutral">{escape(format_date_range(row_value(item, "event_date"), row_value(item, "end_date")))}</span></div><p>{escape(row_value(item, "notes") or "Not eklenmemiş.")}</p><div class="meta-row"><span>{escape(format_event_levels(row_value(item, "level")))}</span></div></article>'


def not_found_page(current_user: dict | None = None, allowed_paths: set[str] | None = None) -> bytes:
    body = '<section class="documents-toolbar dashboard-toolbar"><div><p class="eyebrow">404</p><h2>Sayfa bulunamadı</h2><p>İstediğiniz adres mevcut değil. Sol menüden ana modüllere dönebilirsiniz.</p></div><a class="button" href="/">Dashboard\'a dön</a></section>'
    return layout("Sayfa Bulunamadı", body, "", current_user, allowed_paths)
