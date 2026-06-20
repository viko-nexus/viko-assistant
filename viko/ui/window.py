# viko/ui.py
from __future__ import annotations
import os as _os
import sys
import time
import threading
import socket
import queue as _queue

# Must be set before QApplication / QWebEngine initialises
_os.environ.setdefault(
    "QTWEBENGINE_CHROMIUM_FLAGS",
    "--remote-debugging-port=9222 --no-sandbox --disable-dev-shm-usage"
)

import psutil

from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal, pyqtSlot
from PyQt6.QtGui  import QKeySequence, QShortcut, QIcon, QPixmap, QPainter, QPen, QColor, QAction
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QStackedWidget, QStackedLayout, QLabel, QLineEdit,
    QDialog, QMenu,
)

from viko.ui.theme   import (
    PRI, AMB, TXT,
    pri, F,
    WIN_W, WIN_H, HDR_H, FTR_H, RIGHT_W,
)
from viko.ui.widgets import (
    FloatingArc, _hdr_draw, _ftr_draw,
    HudCanvas, LeftPanel, RightMetricsPanel, ActivityPanel, BootScreen,
)
from viko.ui.browser_panel import BrowserPanel
from viko.core.config import is_configured, get_gemini_key, save_keys


# ─── System Metrics ───────────────────────────────────────────────────────────
class _SysMetrics:
    def __init__(self):
        self._data     = {"cpu": 0.0, "mem": 0.0, "disk": 0.0, "net": 0.0, "latency": 0}
        self._prev_net = psutil.net_io_counters()
        self._ping_ctr = 0
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def snapshot(self) -> dict:
        return dict(self._data)

    def _measure_latency(self) -> int:
        try:
            t0 = time.perf_counter()
            s  = socket.create_connection(("8.8.8.8", 53), timeout=3)
            s.close()
            return max(1, int((time.perf_counter() - t0) * 1000))
        except Exception:
            return self._data["latency"] or 999

    def _run(self):
        while True:
            try:
                self._data["cpu"]  = psutil.cpu_percent(interval=1) / 100
                self._data["mem"]  = psutil.virtual_memory().percent / 100
                try:
                    import platform as _pl
                    import os as _os
                    _dp = "/System/Volumes/Data" if _pl.system() == "Darwin" and _os.path.exists("/System/Volumes/Data") else "/"
                    self._data["disk"] = psutil.disk_usage(_dp).percent / 100
                except Exception:
                    self._data["disk"] = 0.5
                cur  = psutil.net_io_counters()
                sent = (cur.bytes_sent - self._prev_net.bytes_sent) / 1_000_000
                self._data["net"]  = min(1.0, sent / 10)
                self._prev_net = cur
                self._ping_ctr += 1
                if self._ping_ctr % 15 == 1:   # measure every ~15s
                    self._data["latency"] = self._measure_latency()
            except Exception:
                time.sleep(2)


# ─── Setup Overlay ────────────────────────────────────────────────────────────
class SetupOverlay(QWidget):
    done = pyqtSignal(str, str)   # emits (gemini_api_key, owner_passphrase)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: rgba(0,0,0,220);")
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("VIKO INITIALISATION")
        title.setFont(F(14, True)); title.setStyleSheet(f"color: {PRI.name()};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        lbl = QLabel("Gemini API Key")
        lbl.setFont(F(9)); lbl.setStyleSheet(f"color: {TXT.name()};")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl)

        self._key = QLineEdit(); self._key.setEchoMode(QLineEdit.EchoMode.Password)
        self._key.setFont(F(9)); self._key.setFixedWidth(360)
        self._key.setPlaceholderText("AIza...")
        self._key.setStyleSheet("""
            QLineEdit { background: #010d14; color: #8ffcff;
                        border: 1px solid #0d3347; border-radius: 4px; padding: 8px; }
            QLineEdit:focus { border-color: #00d4ff; }
        """)
        lay.addWidget(self._key, alignment=Qt.AlignmentFlag.AlignCenter)

        lbl2 = QLabel("Owner Passphrase (bypass verifikasi suara)")
        lbl2.setFont(F(9)); lbl2.setStyleSheet(f"color: {TXT.name()};")
        lbl2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl2)

        self._pass = QLineEdit(); self._pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._pass.setFont(F(9)); self._pass.setFixedWidth(360)
        self._pass.setPlaceholderText("Kosongkan jika tidak digunakan")
        self._pass.setStyleSheet("""
            QLineEdit { background: #010d14; color: #8ffcff;
                        border: 1px solid #0d3347; border-radius: 4px; padding: 8px; }
            QLineEdit:focus { border-color: #00d4ff; }
        """)
        lay.addWidget(self._pass, alignment=Qt.AlignmentFlag.AlignCenter)

        btn = QPushButton("INITIALISE VIKO")
        btn.setFont(F(9, True)); btn.setFixedWidth(200)
        btn.setStyleSheet(f"""
            QPushButton {{ background: rgba(0,212,255,20); color: {PRI.name()};
                border: 1px solid rgba(0,212,255,80); border-radius: 6px; padding: 8px; }}
            QPushButton:hover {{ background: rgba(0,212,255,50); }}
        """)
        btn.clicked.connect(self._submit)
        self._key.returnPressed.connect(self._submit)
        self._pass.returnPressed.connect(self._submit)
        lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def _submit(self):
        key = self._key.text().strip()
        if key:
            self.done.emit(key, self._pass.text().strip())


# ─── Main Window ──────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    _log_sig     = pyqtSignal(str)
    _state_sig   = pyqtSignal(str)
    _loc_sig     = pyqtSignal(float, float, str)   # lat, lon, label
    _country_sig = pyqtSignal(object)              # list of polygon rings
    _boot_sig    = pyqtSignal(float, str)           # pct, label
    # Thread-safe browser signals (called from executor → queued to main thread)
    _browser_url_sig  = pyqtSignal(str)
    _browser_vis_sig  = pyqtSignal(bool)
    _do_get_content   = pyqtSignal()     # request page text from main thread
    _do_screenshot    = pyqtSignal()     # request screenshot from main thread
    _do_run_js        = pyqtSignal(str)  # run JavaScript in embedded browser
    _do_headless      = pyqtSignal(bool) # set headless mode on browser panel

    on_text_command = None   # set by VikoUI / viko.py
    on_file_command = None   # set by VikoUI / viko.py — receives file path

    def __init__(self):
        super().__init__()
        self.setWindowTitle("VIKO — Virtual Intelligent Knowledge Operator")
        self.resize(WIN_W, WIN_H)
        self.setStyleSheet("background: rgb(0,0,0); color: rgb(200,232,248);")

        self._muted  = False
        self._paused = False
        self._ready  = False
        self._metrics = _SysMetrics()
        self._state_val = "idle"

        self._log_sig.connect(self._on_log)
        self._state_sig.connect(self._apply_state)
        self._loc_sig.connect(self._on_location)
        self._country_sig.connect(self._on_country)
        self._boot_sig.connect(self._on_boot_progress)
        self._browser_url_sig.connect(self.set_browser_url)
        self._browser_vis_sig.connect(self._toggle_browser)
        # Queues for cross-thread results (executor → signal → main thread → queue)
        self._content_q:    _queue.Queue = _queue.Queue(maxsize=1)
        self._screenshot_q: _queue.Queue = _queue.Queue(maxsize=1)
        self._js_q:         _queue.Queue = _queue.Queue(maxsize=1)
        self._do_get_content.connect(self._exec_get_content)
        self._do_screenshot.connect(self._exec_screenshot)
        self._do_run_js.connect(self._exec_run_js)
        self._do_headless.connect(self._exec_headless)

        self._build()
        self._setup_shortcuts()
        self._start_live_feeds()

    # ── Layout ─────────────────────────────────────────────────────────────
    def _build(self):
        self._ui_state = {"panel_visible": False}

        root = QWidget(); self.setCentralWidget(root)
        vlay = QVBoxLayout(root)
        vlay.setContentsMargins(0, 0, 0, 0); vlay.setSpacing(0)

        # ── Header: arc + button overlay stacked together ─────────────────
        hdr_container = QWidget(); hdr_container.setFixedHeight(HDR_H)
        hdr_stk = QStackedLayout(hdr_container)
        hdr_stk.setStackingMode(QStackedLayout.StackingMode.StackAll)
        hdr_stk.setContentsMargins(0, 0, 0, 0); hdr_stk.setSpacing(0)

        # Layer 0 — arc background
        hdr_stk.addWidget(FloatingArc(_hdr_draw, HDR_H, flip=False, state=self._ui_state))

        # Layer 1 — transparent button overlay
        overlay = QWidget()
        overlay.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        overlay.setStyleSheet("background: transparent;")
        ov_lay = QHBoxLayout(overlay)
        _vpad = (HDR_H - 26) // 2
        ov_lay.setContentsMargins(10, _vpad, 10, _vpad); ov_lay.setSpacing(4)

        def _ss(active=False):
            return f"""
                QPushButton {{
                    background: {'rgba(0,212,255,30)' if active else 'rgba(0,212,255,10)'};
                    color: {PRI.name() if active else pri(160).name()};
                    border: 1px solid {'rgba(0,212,255,100)' if active else 'rgba(0,212,255,35)'};
                    border-radius: 4px; padding: 0 6px;
                }}
                QPushButton:hover {{ background: rgba(0,212,255,35); color: {PRI.name()}; }}
            """

        self._btn_ss = _ss

        # TOOLS button — left side
        self._tools_btn = QPushButton("◈  TOOLS")
        self._tools_btn.setFont(F(8, True)); self._tools_btn.setFixedHeight(26)
        self._tools_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tools_btn.setStyleSheet(_ss())
        self._tools_btn.clicked.connect(self._show_tools_menu)
        ov_lay.addWidget(self._tools_btn)

        ov_lay.addStretch(1)   # pushes right buttons to the right edge

        # Action buttons — right side
        self._toggle_btn = QPushButton("◧  ACTIVITY")
        self._toggle_btn.setFixedHeight(26)
        self._toggle_btn.setFont(F(8, True))
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setStyleSheet(_ss()); self._toggle_btn.clicked.connect(self._toggle_panel)
        ov_lay.addWidget(self._toggle_btn)

        self._fs_btn = QPushButton("⛶"); self._fs_btn.setFixedSize(28, 26)
        self._fs_btn.setFont(F(10, True))
        self._fs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fs_btn.setStyleSheet(_ss()); self._fs_btn.clicked.connect(self._toggle_fullscreen)
        ov_lay.addWidget(self._fs_btn)

        self._rst_btn = QPushButton("⟳ RST")
        self._rst_btn.setFixedHeight(26); self._rst_btn.setFixedWidth(52)
        self._rst_btn.setFont(F(8, True))
        self._rst_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rst_btn.setToolTip("Restart VIKO")
        self._rst_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,179,71,12); color: {AMB.name()};
                border: 1px solid rgba(255,179,71,55);
                border-radius: 4px; padding: 0 4px;
            }}
            QPushButton:hover {{ background: rgba(255,179,71,35); color: {AMB.name()}; }}
        """)
        self._rst_btn.clicked.connect(self._restart)
        ov_lay.addWidget(self._rst_btn)

        self._pause_btn = QPushButton("⏸ STOP")
        self._pause_btn.setFixedHeight(26); self._pause_btn.setFixedWidth(60)
        self._pause_btn.setFont(F(8, True))
        self._pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pause_btn.setToolTip("Pause / Resume VIKO")
        self._pause_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,68,68,12); color: rgba(255,68,68,180);
                border: 1px solid rgba(255,68,68,50);
                border-radius: 4px; padding: 0 4px;
            }
            QPushButton:hover { background: rgba(255,68,68,35); color: rgba(255,68,68,230); }
        """)
        self._pause_btn.clicked.connect(self._toggle_pause)
        ov_lay.addWidget(self._pause_btn)

        hdr_stk.addWidget(overlay)
        hdr_stk.setCurrentIndex(1)   # overlay on top — receives mouse events
        vlay.addWidget(hdr_container)

        # Body
        body = QWidget(); blay = QHBoxLayout(body)
        blay.setContentsMargins(0, 0, 0, 0); blay.setSpacing(0)

        self._left = LeftPanel(self._metrics.snapshot)
        blay.addWidget(self._left)

        self._hud     = HudCanvas()
        self._browser = BrowserPanel()
        self._center_stack = QStackedWidget()
        self._center_stack.addWidget(self._hud)      # index 0
        self._center_stack.addWidget(self._browser)  # index 1
        self._center_stack.setCurrentIndex(0)
        blay.addWidget(self._center_stack, 1)
        self._browser.page_loaded.connect(self._on_page_loaded)
        self._browser.minimize_requested.connect(lambda: self._toggle_browser(False))

        # Right column (content only — buttons are in the top_bar above)
        self._right_col_widget = QWidget()
        right_col = self._right_col_widget
        right_col.setFixedWidth(RIGHT_W)
        rcol = QVBoxLayout(right_col)
        rcol.setContentsMargins(0, 0, 0, 0); rcol.setSpacing(0)

        self._right_stack = QStackedWidget()
        self._right_metrics = RightMetricsPanel(self._metrics.snapshot)
        self._activity       = ActivityPanel()
        self._activity._drop.file_selected.connect(self._on_file_selected)
        self._right_stack.addWidget(self._right_metrics)   # index 0
        self._right_stack.addWidget(self._activity)         # index 1
        self._right_stack.setCurrentIndex(0)
        rcol.addWidget(self._right_stack, 1)
        blay.addWidget(right_col)
        vlay.addWidget(body, 1)

        # Footer
        self._ftr = FloatingArc(_ftr_draw, FTR_H, flip=True,
                                on_click=self._toggle_panel, state=self._ui_state)
        vlay.addWidget(self._ftr)

        # Setup overlay — skip if key already in .env
        if is_configured():
            self._overlay = None
            self._ready = True
            import os
            os.environ.setdefault("GEMINI_API_KEY", get_gemini_key())
        else:
            self._overlay = SetupOverlay(root)
            self._overlay.setGeometry(0, 0, WIN_W, WIN_H)
            self._overlay.done.connect(self._on_api_key)
            self._overlay.show()

        # Boot screen — shown during startup (only when API key already configured)
        if is_configured():
            self._boot_screen = BootScreen(root)
            self._boot_screen.setGeometry(0, 0, WIN_W, WIN_H)
            self._boot_screen.finished.connect(self._on_boot_finished)
            self._boot_screen.raise_()
            self._boot_screen.show()
        else:
            self._boot_screen = None

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "_overlay") and self._overlay:
            self._overlay.setGeometry(0, 0, self.width(), self.height())
        if hasattr(self, "_boot_screen") and self._boot_screen:
            self._boot_screen.setGeometry(0, 0, self.width(), self.height())

    def _on_boot_progress(self, pct: float, label: str):
        if hasattr(self, "_boot_screen") and self._boot_screen:
            self._boot_screen.set_progress(pct, label)

    def _on_boot_finished(self):
        if hasattr(self, "_boot_screen") and self._boot_screen:
            self._boot_screen.hide()
            self._boot_screen.deleteLater()
            self._boot_screen = None
        if self._ready and not self.isVisible():
            pass  # already handled
        state = getattr(self, "_state_val", "LISTENING")
        if state in ("THINKING", "IDLE"):
            state = "LISTENING"
        self._apply_state(state)
        if state == "OFFLINE":
            self._activity.append_log("SYS: Gemini offline — mode offline aktif.")
        else:
            self._activity.append_log("SYS: Viko online.")

    def set_boot_progress(self, pct: float, label: str):
        self._boot_sig.emit(pct, label)

    # ── Shortcuts ──────────────────────────────────────────────────────────
    def _setup_shortcuts(self):
        QShortcut(QKeySequence("F4"),  self).activated.connect(self._toggle_mute)
        QShortcut(QKeySequence("F11"), self).activated.connect(self._toggle_fullscreen)

    # ── Panel toggle + fullscreen ──────────────────────────────────────────
    def _toggle_panel(self):
        self._ui_state["panel_visible"] = not self._ui_state["panel_visible"]
        v = self._ui_state["panel_visible"]
        self._right_stack.setCurrentIndex(1 if v else 0)
        self._toggle_btn.setText("◨  METRICS" if v else "◧  ACTIVITY")
        self._toggle_btn.setStyleSheet(self._btn_ss(v))
        self._ftr.update()

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal(); self._fs_btn.setStyleSheet(self._btn_ss(False))
        else:
            self.showFullScreen(); self._fs_btn.setStyleSheet(self._btn_ss(True))

    def _show_tools_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: #010d14;
                border: 1px solid rgba(0,212,255,70);
                border-radius: 6px;
                color: rgba(200,232,248,220);
                padding: 4px 0;
            }}
            QMenu::item {{
                padding: 7px 22px 7px 14px;
                font-size: 11px;
                font-family: 'Courier New';
            }}
            QMenu::item:selected {{
                background: rgba(0,212,255,28);
                color: {PRI.name()};
            }}
            QMenu::separator {{
                height: 1px;
                background: rgba(0,212,255,25);
                margin: 3px 8px;
            }}
        """)
        browser_act = QAction("🌐   Browser", self)
        menu.addAction(browser_act)
        menu.addSeparator()
        ws_act = QAction("📁   Workspace", self)
        menu.addAction(ws_act)

        pos = self._tools_btn.mapToGlobal(QPoint(0, self._tools_btn.height()))
        action = menu.exec(pos)

        if action == browser_act:
            self._toggle_browser(True)
        elif action == ws_act:
            from viko.core.workspace import WORKSPACE
            self._browser.navigate(WORKSPACE.as_uri())
            self._toggle_browser(True)

    @pyqtSlot(bool)
    def _toggle_browser(self, visible: bool) -> None:
        self._center_stack.setCurrentIndex(1 if visible else 0)
        # Full-width mode: hide/show side panels
        self._left.setVisible(not visible)
        self._right_col_widget.setVisible(not visible)
        self._center_stack.update()
        # Highlight the TOOLS button when browser active
        self._tools_btn.setStyleSheet(f"""
            QPushButton {{
                background: {'rgba(0,212,255,25)' if visible else 'transparent'};
                color: {PRI.name() if visible else pri(160).name()};
                border: {'1px solid rgba(0,212,255,70)' if visible else 'none'};
                padding: 0 8px; border-radius: 3px;
            }}
            QPushButton:hover {{ background: rgba(0,212,255,18); color: {PRI.name()}; }}
            QPushButton:pressed {{ background: rgba(0,212,255,30); }}
        """)
        # Auto-start agent-browser in background when browser becomes visible
        if visible:
            from viko.ui.agent_browser import get_server
            get_server().auto_start_in_background()

    @pyqtSlot(bool)
    def _exec_headless(self, enabled: bool):
        self._browser.headless_mode = enabled

    def _on_page_loaded(self, url: str):
        self._tools_btn.setToolTip(f"Browser: {url[:60]}")

    @pyqtSlot()
    def _exec_get_content(self):
        try:
            self._content_q.get_nowait()
        except _queue.Empty:
            pass

        def _cb(text):
            try:
                self._content_q.put_nowait(text)
            except _queue.Full:
                pass

        self._browser.page().toPlainText(_cb)

    @pyqtSlot()
    def _exec_screenshot(self):
        try:
            self._screenshot_q.get_nowait()
        except _queue.Empty:
            pass
        from viko.core.workspace import WORKSPACE, ensure_dirs
        ensure_dirs()
        px  = self._browser.grab()
        out = WORKSPACE / "documents" / "screenshot_latest.png"
        px.save(str(out))
        try:
            self._screenshot_q.put_nowait(out.read_bytes())
        except _queue.Full:
            pass

    @pyqtSlot(str)
    def _exec_run_js(self, code: str):
        try:
            self._js_q.get_nowait()
        except _queue.Empty:
            pass

        def _cb(result):
            try:
                self._js_q.put_nowait(result)
            except _queue.Full:
                pass

        self._browser.page().runJavaScript(code, _cb)

    @pyqtSlot(str)
    def set_browser_url(self, url: str):
        self._browser.navigate(url)

    def set_browser_visible(self, visible: bool):
        self._toggle_browser(visible)

    def _restart(self):
        dlg = QDialog(self, Qt.WindowType.FramelessWindowHint)
        dlg.setFixedSize(300, 130)
        dlg.setStyleSheet("""
            QDialog {
                background: #010d14;
                border: 1px solid rgba(255,179,71,120);
                border-radius: 8px;
            }
        """)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 18, 20, 14); lay.setSpacing(10)

        title = QLabel("⟳  RESTART VIKO")
        title.setFont(F(11, True))
        title.setStyleSheet(f"color: {AMB.name()}; background: transparent;")
        lay.addWidget(title)

        msg = QLabel("Restart aplikasi sekarang?")
        msg.setFont(F(9))
        msg.setStyleSheet(f"color: {TXT.name()}; background: transparent;")
        lay.addWidget(msg)

        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        _btn_style = lambda c, a: f"""
            QPushButton {{
                background: rgba({c},15); color: rgba({c},220);
                border: 1px solid rgba({c},80); border-radius: 4px;
                padding: 5px 0;
            }}
            QPushButton:hover {{ background: rgba({c},{a}); }}
        """
        yes = QPushButton("Ya, Restart"); yes.setFont(F(9, True))
        yes.setStyleSheet(_btn_style("255,179,71", 50))
        no  = QPushButton("Batal"); no.setFont(F(9))
        no.setStyleSheet(_btn_style("0,212,255", 40))

        yes.clicked.connect(dlg.accept)
        no.clicked.connect(dlg.reject)
        btn_row.addWidget(no); btn_row.addWidget(yes)
        lay.addLayout(btn_row)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            import os
            QApplication.instance().quit()
            os.execv(sys.executable, [sys.executable] + sys.argv)

    # ── Pause/Stop ────────────────────────────────────────────────────────
    def _toggle_pause(self):
        self._paused = not self._paused
        if self._paused:
            self._hud.set_state("PAUSED")
            self._left.set_paused(True)
            self._activity.set_paused(True)
            self._pause_btn.setText("▶ START")
            self._pause_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(0,255,159,15);
                    color: rgba(0,255,159,210);
                    border: 1px solid rgba(0,255,159,70);
                    border-radius: 4px; padding: 0 4px;
                }
                QPushButton:hover { background: rgba(0,255,159,40); color: rgba(0,255,159,255); }
            """)
            self._activity.append_log("SYS: Viko paused — tidak merespon input.")
        else:
            self._left.set_paused(False)
            self._activity.set_paused(False)
            self._hud.set_state(self._state_val)
            self._pause_btn.setText("⏸ STOP")
            self._pause_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255,68,68,12);
                    color: rgba(255,68,68,180);
                    border: 1px solid rgba(255,68,68,50);
                    border-radius: 4px; padding: 0 4px;
                }
                QPushButton:hover { background: rgba(255,68,68,35); color: rgba(255,68,68,230); }
            """)
            self._activity.append_log("SYS: Viko resumed — siap merespon.")

    # ── Mute ──────────────────────────────────────────────────────────────
    def _toggle_mute(self):
        self._muted = not self._muted
        self._hud._muted = self._muted
        if self._muted:
            self._hud.set_state("MUTED")
        else:
            self._hud.set_state(self._state_val)

    # ── State + Log ───────────────────────────────────────────────────────
    def _apply_state(self, state: str):
        self._state_val = state
        if not self._muted and not self._paused:
            self._hud.set_state(state)
        online = state not in ("IDLE", "OFFLINE")
        self._left.set_online(online)
        self._right_metrics.set_gemini_online(online)

    def _on_log(self, text: str):
        self._activity.append_log(text)
        self._right_metrics.inc_ops()

    # ── API key ───────────────────────────────────────────────────────────
    def _on_api_key(self, key: str, passphrase: str):
        save_keys(gemini_api_key=key, owner_passphrase=passphrase)
        self._ready = True
        if self._overlay:
            self._overlay.hide(); self._overlay = None
        self._apply_state("LISTENING")
        self._activity.append_log("SYS: Initialised. Viko online.")

    def _on_file_selected(self, path: str):
        if self.on_file_command:
            import threading as _t
            _t.Thread(target=self.on_file_command, args=(path,), daemon=True).start()
        elif self.on_text_command:
            # fallback: plain text notification if no dedicated handler
            from pathlib import Path as _Path
            p = _Path(path); size = p.stat().st_size
            size_str = (f"{size//1_048_576}MB" if size >= 1_048_576
                        else f"{size//1024}KB" if size >= 1024 else f"{size}B")
            import threading as _t
            _t.Thread(target=self.on_text_command,
                      args=(f"[FILE_UPLOADED] {p.name} ({size_str}) sudah diupload — mau diapakan?",),
                      daemon=True).start()

    # ── Live data feeds ───────────────────────────────────────────────────
    def _start_live_feeds(self):
        lat_timer = QTimer(self)
        lat_timer.timeout.connect(self._push_latency)
        lat_timer.start(5000)

        # Manual coordinates from .env take priority — skip IP and CoreLocation
        from viko.core.config import get_location as _get_loc
        manual = _get_loc()
        if manual:
            lat, lon = manual
            la_d, la_m = int(abs(lat)), int((abs(lat) % 1) * 60)
            lo_d, lo_m = int(abs(lon)), int((abs(lon) % 1) * 60)
            la_s = f"{la_d:02d}°{la_m:02d}′{'N' if lat >= 0 else 'S'}"
            lo_s = f"{lo_d:03d}°{lo_m:02d}′{'E' if lon >= 0 else 'W'}"
            self._loc_sig.emit(lat, lon, f"CFG  {la_s}  {lo_s}")
            threading.Thread(target=self._fetch_country_from_gps, args=(lat, lon), daemon=True).start()
        else:
            # IP fallback: runs in background, also fetches country polygon
            threading.Thread(target=self._fetch_location, daemon=True).start()
            # CoreLocation on main thread (accurate GPS/WiFi) — needs macOS permission
            QTimer.singleShot(800, self._start_corelocation)

    def _start_corelocation(self):
        """
        Start macOS CoreLocation on the main thread.

        Non-bundle Python apps don't receive the system permission dialog —
        the user must grant Terminal (or python3) location access manually in
        System Settings → Privacy & Security → Location Services.
        We check the current status and guide the user accordingly.
        """
        from viko.core.logger import get_logger as _gl
        _log = _gl(__name__)
        try:
            import objc

            cl = {}
            objc.loadBundle(
                'CoreLocation',
                bundle_path='/System/Library/Frameworks/CoreLocation.framework',
                module_globals=cl,
            )
            CLLocationManager = cl['CLLocationManager']
            try:
                from Foundation import NSObject
            except ImportError:
                NSObject = objc.lookUpClass('NSObject')

            # Authorization status constants
            AUTH_NOT_DETERMINED = 0
            AUTH_DENIED         = 2
            AUTH_AUTHORIZED     = 3   # macOS "always"
            AUTH_WHEN_IN_USE    = 4

            parent = self

            def _fmt_label(lat, lon):
                la_d, la_m = int(abs(lat)), int((abs(lat) % 1) * 60)
                lo_d, lo_m = int(abs(lon)), int((abs(lon) % 1) * 60)
                la_s = f"{la_d:02d}°{la_m:02d}′{'N' if lat >= 0 else 'S'}"
                lo_s = f"{lo_d:03d}°{lo_m:02d}′{'E' if lon >= 0 else 'W'}"
                return f"GPS  {la_s}  {lo_s}"

            class _VikoCLDelegate(NSObject):

                def locationManager_didUpdateLocations_(self_d, mgr, locs):
                    if not locs:
                        return
                    loc   = locs[-1]
                    coord = loc.coordinate()
                    try:
                        lat, lon = float(coord.latitude), float(coord.longitude)
                    except AttributeError:
                        lat, lon = float(coord[0]), float(coord[1])
                    parent._loc_sig.emit(lat, lon, _fmt_label(lat, lon))
                    import threading as _t
                    _t.Thread(
                        target=parent._fetch_country_from_gps,
                        args=(lat, lon),
                        daemon=True,
                    ).start()

                locationManager_didUpdateLocations_ = objc.selector(
                    locationManager_didUpdateLocations_,
                    selector=b'locationManager:didUpdateLocations:',
                    signature=b'v@:@@',
                )

                def locationManagerDidChangeAuthorization_(self_d, mgr):
                    status = mgr.authorizationStatus()
                    if status in (AUTH_AUTHORIZED, AUTH_WHEN_IN_USE):
                        mgr.startUpdatingLocation()
                    elif status == AUTH_DENIED:
                        parent._log_sig.emit(
                            "SYS: Lokasi: akses ditolak. Buka System Settings → "
                            "Privacy & Security → Location Services → aktifkan Terminal."
                        )

                locationManagerDidChangeAuthorization_ = objc.selector(
                    locationManagerDidChangeAuthorization_,
                    selector=b'locationManagerDidChangeAuthorization:',
                    signature=b'v@:@',
                )

                def locationManager_didFailWithError_(self_d, mgr, err):
                    # Code=0 (kCLErrorLocationUnknown) is transient — not a real failure
                    _log.debug("CoreLocation: %s", err)

                locationManager_didFailWithError_ = objc.selector(
                    locationManager_didFailWithError_,
                    selector=b'locationManager:didFailWithError:',
                    signature=b'v@:@@',
                )

            self._cl_delegate = _VikoCLDelegate.new()
            self._cl_manager  = CLLocationManager.new()
            self._cl_manager.setDelegate_(self._cl_delegate)
            self._cl_manager.setDistanceFilter_(50.0)
            self._cl_manager.setDesiredAccuracy_(100.0)  # kCLLocationAccuracyHundredMeters

            # Use instance method — class method is deprecated on macOS 14+
            status = self._cl_manager.authorizationStatus()
            if status in (AUTH_AUTHORIZED, AUTH_WHEN_IN_USE):
                self._cl_manager.startUpdatingLocation()
            elif status == AUTH_NOT_DETERMINED:
                self._cl_manager.requestWhenInUseAuthorization()
            elif status == AUTH_DENIED:
                self._log_sig.emit(
                    "SYS: Lokasi GPS diblokir. Buka VIKO.app agar permission dialog muncul."
                )

            labels = {0: "not_determined", 1: "restricted", 2: "denied",
                      3: "authorized_always", 4: "authorized_when_in_use"}
            _log.info("CoreLocation auth status: %s (%s)", status, labels.get(status, "unknown"))

        except Exception as e:
            _log.warning("CoreLocation unavailable: %s", e)

    def _fetch_country_from_gps(self, lat: float, lon: float):
        try:
            import urllib.request
            import json as _json
            url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
            req = urllib.request.Request(url, headers={"User-Agent": "VIKO/1.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                d = _json.loads(r.read())
            cc2 = d.get("address", {}).get("country_code", "").upper()
            if cc2:
                polys = self._fetch_country_polys(cc2)
                if polys:
                    self._country_sig.emit(polys)
        except Exception:
            pass

    def _push_latency(self):
        ms = self._metrics.snapshot().get("latency", 0)
        if ms > 0:
            self._right_metrics.set_latency(ms)

    # ISO alpha-2 → alpha-3 for world.geo.json filenames
    _A2_TO_A3 = {
        "ID": "IDN", "MY": "MYS", "SG": "SGP", "TH": "THA", "PH": "PHL",
        "VN": "VNM", "MM": "MMR", "BN": "BRN", "KH": "KHM", "LA": "LAO",
        "US": "USA", "CA": "CAN", "GB": "GBR", "AU": "AUS", "NZ": "NZL",
        "JP": "JPN", "CN": "CHN", "KR": "KOR", "IN": "IND", "PK": "PAK",
        "DE": "DEU", "FR": "FRA", "NL": "NLD", "IT": "ITA", "ES": "ESP",
        "SA": "SAU", "AE": "ARE", "TR": "TUR", "EG": "EGY", "IR": "IRN",
        "RU": "RUS", "BR": "BRA", "MX": "MEX", "ZA": "ZAF", "NG": "NGA",
        "BD": "BGD", "LK": "LKA", "MV": "MDV", "NP": "NPL",
    }

    def _fetch_location(self):
        try:
            import urllib.request
            import json as _json
            with urllib.request.urlopen("http://ip-api.com/json/", timeout=6) as r:
                d = _json.loads(r.read())
            lat  = float(d.get("lat", 3.14))
            lon  = float(d.get("lon", 101.69))
            cc2  = d.get("countryCode", "")
            city = d.get("city", "")
            la_d, la_m = int(abs(lat)), int((abs(lat) % 1) * 60)
            lo_d, lo_m = int(abs(lon)), int((abs(lon) % 1) * 60)
            la_s = f"{la_d:02d}°{la_m:02d}′{'N' if lat >= 0 else 'S'}"
            lo_s = f"{lo_d:03d}°{lo_m:02d}′{'E' if lon >= 0 else 'W'}"
            city_str = f"{city.upper()}, {cc2}" if city else cc2
            self._loc_sig.emit(lat, lon, f"IP:{city_str}  {la_s}  {lo_s}")
            # Fetch country polygon
            if cc2:
                polys = self._fetch_country_polys(cc2)
                if polys:
                    self._country_sig.emit(polys)
        except Exception:
            pass

    def _fetch_country_polys(self, cc2: str) -> list:
        import urllib.request
        import json as _json
        from pathlib import Path
        cc3 = self._A2_TO_A3.get(cc2)
        if not cc3:
            return []
        cache = Path.home() / ".viko" / "geo_cache" / f"{cc3}.json"
        cache.parent.mkdir(parents=True, exist_ok=True)
        try:
            if cache.exists():
                raw = cache.read_bytes()
            else:
                url = (f"https://raw.githubusercontent.com/johan/world.geo.json"
                       f"/master/countries/{cc3}.geo.json")
                req = urllib.request.Request(url, headers={"User-Agent": "VIKO/1.0"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    raw = r.read()
                cache.write_bytes(raw)
            data = _json.loads(raw)
        except Exception:
            return []

        polys = []
        for feat in data.get("features", []):
            geom  = feat.get("geometry", {})
            gtype = geom.get("type", "")
            coords = geom.get("coordinates", [])
            if gtype == "Polygon":
                polys.append([(c[0], c[1]) for c in coords[0]])
            elif gtype == "MultiPolygon":
                for part in coords:
                    polys.append([(c[0], c[1]) for c in part[0]])
        return polys

    def _on_location(self, lat: float, lon: float, label: str):
        self._left.set_location(lat, lon, label)

    def _on_country(self, polys: list):
        self._left.set_country_polys(polys)


# ─── Public Facade (identical interface to old ui.py) ─────────────────────────
class _RootShim:
    def __init__(self, app): self._app = app
    def mainloop(self): self._app.exec()
    def protocol(self, *_): pass


def _make_app_icon() -> QIcon:
    from pathlib import Path
    icon_path = Path(__file__).resolve().parent.parent.parent / "assets" / "icon.png"
    if icon_path.exists():
        return QIcon(str(icon_path))

    # Fallback: draw programmatically if file missing
    sz = 256
    px = QPixmap(sz, sz)
    px.fill(QColor(0, 0, 0, 0))
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    cx = cy = sz // 2
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 8, 18))
    p.drawEllipse(4, 4, sz - 8, sz - 8)
    for r, alpha, lw in [(108, 70, 2.5), (84, 100, 2), (60, 130, 2), (38, 90, 1.5)]:
        p.setPen(QPen(QColor(0, 212, 255, alpha), lw))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)
    from PyQt6.QtGui import QFont, QFontMetrics
    font = QFont("Courier New", 88, QFont.Weight.Bold)
    p.setFont(font)
    p.setPen(QColor(0, 212, 255, 230))
    fm = QFontMetrics(font)
    p.drawText(cx - fm.horizontalAdvance("V") // 2, cy + fm.ascent() // 2 - 4, "V")
    p.end()
    return QIcon(px)


def _set_macos_app_icon(qt_icon: QIcon) -> None:
    """Push the Qt icon to NSApplication so dock and title bar use the same image."""
    try:
        import tempfile
        import os as _os
        from AppKit import NSApplication, NSImage
        px = qt_icon.pixmap(256, 256)
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        px.save(tmp.name, "PNG")
        ns_img = NSImage.alloc().initWithContentsOfFile_(tmp.name)
        if ns_img:
            NSApplication.sharedApplication().setApplicationIconImage_(ns_img)
        _os.unlink(tmp.name)
    except Exception:
        pass


class VikoUI:
    def __init__(self, face_path: str, size=None):
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        icon = _make_app_icon()
        self._app.setWindowIcon(icon)
        self._win = MainWindow()
        self._win.setWindowIcon(icon)
        _set_macos_app_icon(icon)
        self._win.show()
        self.root = _RootShim(self._app)

    @property
    def muted(self) -> bool: return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win._muted: self._win._toggle_mute()

    @property
    def paused(self) -> bool: return self._win._paused

    @paused.setter
    def paused(self, v: bool):
        if v != self._win._paused: self._win._toggle_pause()

    @property
    def current_file(self) -> str | None:
        return self._win._activity.current_file()

    @property
    def on_text_command(self): return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb):
        self._win.on_text_command = cb
        self._win._activity.on_text_command_changed(cb)

    @property
    def on_file_command(self): return self._win.on_file_command

    @on_file_command.setter
    def on_file_command(self, cb):
        self._win.on_file_command = cb

    @property
    def headless_mode(self) -> bool:
        return self._win._browser.headless_mode

    @headless_mode.setter
    def headless_mode(self, enabled: bool):
        self._win._do_headless.emit(bool(enabled))

    def set_state(self, state: str): self._win._state_sig.emit(state)
    def write_log(self, text: str):  self._win._log_sig.emit(text)
    def set_boot_progress(self, pct: float, label: str): self._win.set_boot_progress(pct, label)
    def set_browser_url(self, url: str):
        self._win._browser_url_sig.emit(url)
    def toggle_browser(self, visible: bool | None = None):
        self._win._browser_vis_sig.emit(True if visible is None else bool(visible))

    def run_js(self, code: str, timeout: float = 10.0):
        self._win._do_run_js.emit(code)
        try:
            return self._win._js_q.get(timeout=timeout)
        except Exception:
            return None

    def get_page_content(self, timeout: float = 10.0) -> str:
        self._win._do_get_content.emit()
        try:
            return self._win._content_q.get(timeout=timeout)
        except Exception:
            return ""

    def take_screenshot(self, timeout: float = 10.0) -> bytes:
        self._win._do_screenshot.emit()
        try:
            return self._win._screenshot_q.get(timeout=timeout)
        except Exception:
            return b""

    def wait_for_api_key(self):
        while not self._win._ready: time.sleep(0.1)
    def start_speaking(self): self.set_state("SPEAKING")
    def stop_speaking(self):
        if not self.muted: self.set_state("LISTENING")
