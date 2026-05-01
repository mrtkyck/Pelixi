from __future__ import annotations

import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk


class SplashScreen:
    def __init__(
        self,
        logo_path: Path | None = None,
        brand_name: str = "PELIXI",
        subtitle: str = "İŞ PLATFORMU",
        min_duration_ms: int = 1800,
        timeout_ms: int = 12000,
    ) -> None:
        self.logo_path = Path(logo_path) if logo_path else None
        self.brand_name = brand_name
        self.subtitle = subtitle
        self.min_duration_ms = min_duration_ms
        self.timeout_ms = timeout_ms
        self._root: tk.Tk | None = None
        self._progress: ttk.Progressbar | None = None
        self._logo_image = None
        self._start_time = 0.0
        self._check_ready = None
        self._error: Exception | None = None
        self._closed = False

    def show_until(self, check_ready) -> None:
        self._check_ready = check_ready
        self._start_time = time.monotonic()
        self._root = tk.Tk()
        self._root.withdraw()
        self._root.overrideredirect(True)
        self._root.configure(bg="#07111f")
        self._root.attributes("-topmost", True)
        try:
            self._root.attributes("-alpha", 0.0)
        except tk.TclError:
            pass

        shell = tk.Frame(
            self._root,
            bg="#07111f",
            padx=38,
            pady=34,
            highlightthickness=1,
            highlightbackground="#163154",
        )
        shell.pack(fill="both", expand=True)

        logo_wrap = tk.Frame(shell, bg="#07111f")
        logo_wrap.pack(fill="x", pady=(2, 18))

        if self.logo_path and self.logo_path.exists():
            try:
                self._logo_image = tk.PhotoImage(file=str(self.logo_path))
                image_width = self._logo_image.width()
                image_height = self._logo_image.height()
                width_ratio = max(1, -(-image_width // 320))
                height_ratio = max(1, -(-image_height // 124))
                sample_ratio = max(width_ratio, height_ratio)
                if sample_ratio > 1:
                    self._logo_image = self._logo_image.subsample(sample_ratio, sample_ratio)
            except tk.TclError:
                self._logo_image = None

        if self._logo_image is not None:
            tk.Label(logo_wrap, image=self._logo_image, bg="#07111f").pack()
        else:
            tk.Label(
                logo_wrap,
                text="P",
                bg="#07111f",
                fg="#2d7cff",
                font=("Segoe UI Semibold", 54),
            ).pack()

        tk.Label(
            shell,
            text=self.brand_name,
            bg="#07111f",
            fg="#f7fbff",
            font=("Segoe UI Semibold", 24),
        ).pack()
        tk.Label(
            shell,
            text=self.subtitle,
            bg="#07111f",
            fg="#74a8ff",
            font=("Segoe UI", 12),
        ).pack(pady=(6, 18))

        style = ttk.Style(self._root)
        try:
            style.theme_use("default")
        except tk.TclError:
            pass
        style.configure(
            "Pelixi.Horizontal.TProgressbar",
            troughcolor="#11233b",
            background="#2d7cff",
            bordercolor="#11233b",
            lightcolor="#5aa8ff",
            darkcolor="#1f63d8",
            thickness=5,
        )

        self._progress = ttk.Progressbar(
            shell,
            mode="indeterminate",
            length=280,
            style="Pelixi.Horizontal.TProgressbar",
        )
        self._progress.pack(pady=(0, 4))
        self._progress.start(10)

        tk.Label(
            shell,
            text="Yükleniyor...",
            bg="#07111f",
            fg="#8ba0bf",
            font=("Segoe UI", 10),
        ).pack()

        self._root.update_idletasks()
        width = 420
        height = 320
        screen_width = self._root.winfo_screenwidth()
        screen_height = self._root.winfo_screenheight()
        x = int((screen_width - width) / 2)
        y = int((screen_height - height) / 2)
        self._root.geometry(f"{width}x{height}+{x}+{y}")
        self._root.deiconify()

        self._fade_in(0.0)
        self._tick()
        self._root.mainloop()

        if self._error:
            raise self._error

    def close(self) -> None:
        if self._closed or not self._root:
            return
        self._closed = True
        if self._progress:
            self._progress.stop()
        self._root.destroy()

    def _fade_in(self, alpha: float) -> None:
        if not self._root or self._closed:
            return
        try:
            self._root.attributes("-alpha", min(alpha, 1.0))
        except tk.TclError:
            return
        if alpha < 1.0:
            self._root.after(24, lambda: self._fade_in(alpha + 0.1))

    def _tick(self) -> None:
        if not self._root or self._closed:
            return

        elapsed_ms = int((time.monotonic() - self._start_time) * 1000)
        if elapsed_ms >= self.timeout_ms:
            self._error = RuntimeError("Pelixi sunucusu zamanında başlatılamadı.")
            self.close()
            return

        ready = False
        try:
            ready = bool(self._check_ready()) if self._check_ready else True
        except Exception:
            ready = False

        if ready and elapsed_ms >= self.min_duration_ms:
            self.close()
            return

        self._root.after(120, self._tick)
