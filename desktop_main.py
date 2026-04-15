from __future__ import annotations

import os
import threading
import time
from urllib.request import urlopen
from pathlib import Path

import webview

from app.server import run_server


HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}/"
WEBVIEW_STORAGE = Path(os.getenv("LOCALAPPDATA", ".")) / "MyNotes" / "webview"


def _wait_for_server(timeout: float = 12.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(URL, timeout=1):
                return
        except Exception:
            time.sleep(0.25)
    raise RuntimeError("MyNotes sunucusu başlatılamadı.")


def main() -> None:
    WEBVIEW_STORAGE.mkdir(parents=True, exist_ok=True)
    server_thread = threading.Thread(
        target=run_server,
        kwargs={"host": HOST, "port": PORT},
        daemon=True,
        name="MyNotesServer",
    )
    server_thread.start()
    _wait_for_server()
    window = webview.create_window(
        "MyNotes",
        URL,
        width=1440,
        height=920,
        min_size=(1100, 760),
        text_select=True,
    )
    webview.start(gui="edgechromium", private_mode=False, storage_path=str(WEBVIEW_STORAGE))


if __name__ == "__main__":
    main()
