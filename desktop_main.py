from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from urllib.request import urlopen

import webview

from app.server import run_server
from ui.splash_screen import SplashScreen


HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}/"
APP_BRAND = "Pelixi"
# Mevcut kullanıcı verisini bozmamak için depolama klasörünü aynı tutuyoruz.
APP_STORAGE_NAME = "MyNotes"
WEBVIEW_STORAGE = Path(os.getenv("LOCALAPPDATA", ".")) / APP_STORAGE_NAME / "webview"
LOGO_PATH = Path(__file__).resolve().parent / "assets" / "pelixi-logo-dark.png"


def _is_server_ready() -> bool:
    try:
        with urlopen(URL, timeout=1):
            return True
    except Exception:
        return False


def _wait_for_server(timeout: float = 12.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _is_server_ready():
            return
        time.sleep(0.25)
    raise RuntimeError("Pelixi sunucusu başlatılamadı.")


def main() -> None:
    WEBVIEW_STORAGE.mkdir(parents=True, exist_ok=True)
    server_thread = threading.Thread(
        target=run_server,
        kwargs={"host": HOST, "port": PORT},
        daemon=True,
        name="PelixiServer",
    )
    server_thread.start()

    try:
        splash = SplashScreen(
            logo_path=LOGO_PATH,
            brand_name="PELIXI",
            subtitle="İŞ PLATFORMU",
            min_duration_ms=1800,
            timeout_ms=12000,
        )
        splash.show_until(_is_server_ready)
    except Exception:
        _wait_for_server()

    webview.create_window(
        APP_BRAND,
        URL,
        width=1440,
        height=920,
        min_size=(1100, 760),
        text_select=True,
    )
    webview.start(gui="edgechromium", private_mode=False, storage_path=str(WEBVIEW_STORAGE))


if __name__ == "__main__":
    main()
