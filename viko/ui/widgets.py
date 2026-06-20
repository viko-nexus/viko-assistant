# viko/ui_widgets.py
from __future__ import annotations
import math
import time
import os
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import (
    QColor, QPainter, QPainterPath, QPen, QBrush,
    QLinearGradient, QRadialGradient, QConicalGradient, QFontMetrics, QFont,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel,
    QLineEdit, QPushButton,
)

from viko.ui.theme import (
    _c, BG, DIM, PRI, AMB, SUC,
    pri, amb, suc, F,
    LEFT_W, RIGHT_W, _WORLD_POLYS,
)


class FloatingArc(QWidget):
    """Centered trapezoidal arch panel floating with dark space on left/right."""

    def __init__(self, draw_fn, height: int, flip: bool = False,
                 on_click=None, state: dict | None = None, parent=None):
        super().__init__(parent)
        self._draw     = draw_fn
        self._flip     = flip
        self._tick     = 0
        self._on_click = on_click
        self._state    = state or {}
        self.setFixedHeight(height)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        t = QTimer(self); t.timeout.connect(self._step); t.start(50)

    def _step(self): self._tick += 1; self.update()

    def _panel_btn_rect(self):
        W  = self.width()
        pw = int(W * 0.50)
        px = (W - pw) // 2
        bx = px + pw - 30 - 96
        return bx, bx + 96

    def mousePressEvent(self, e):
        if self._on_click and self._flip:
            x = int(e.position().x())
            x1, x2 = self._panel_btn_rect()
            if x1 <= x <= x2:
                self._on_click()

    def mouseMoveEvent(self, e):
        if self._flip:
            x = int(e.position().x())
            x1, x2 = self._panel_btn_rect()
            self.setCursor(Qt.CursorShape.PointingHandCursor
                           if x1 <= x <= x2 else Qt.CursorShape.ArrowCursor)

    def _path(self) -> QPainterPath:
        W, H = self.width(), self.height()
        pw    = int(W * 0.50)
        px    = (W - pw) // 2
        slant = 30
        pad   = 3
        path = QPainterPath()
        if not self._flip:
            path.moveTo(px,              pad)
            path.lineTo(px + pw,         pad)
            path.lineTo(px + pw - slant, H - pad - 6)
            path.quadTo(W / 2,           H - pad + 10,
                        px + slant,      H - pad - 6)
            path.closeSubpath()
        else:
            path.moveTo(px,           H - pad)
            path.lineTo(px + slant,   pad + 6)
            path.quadTo(W / 2,        pad - 8,
                        px + pw - slant, pad + 6)
            path.lineTo(px + pw,      H - pad)
            path.closeSubpath()
        return path

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        path = self._path()
        g = QLinearGradient(0, 0, 0, H)
        g.setColorAt(0, _c(6, 18, 34, 240))
        g.setColorAt(1, _c(3, 10, 20, 250))
        p.fillPath(path, QBrush(g))
        p.setPen(QPen(pri(16), 8)); p.drawPath(path)
        alpha = int(75 + 50 * math.sin(self._tick * 0.09))
        p.setPen(QPen(pri(alpha), 1.3)); p.drawPath(path)
        self._draw(p, W, H, self._tick, self._state)
        p.end()


def _hdr_draw(p: QPainter, W: int, H: int, tick: int, state: dict = {}):
    pw    = int(W * 0.50)
    px    = (W - pw) // 2
    slant = 30
    x1    = px + slant + 10
    x2    = px + pw - slant - 10
    cx    = W // 2

    p.setFont(F(10, True)); p.setPen(pri(100))
    p.drawText(x1, H // 2 - 1, "B.0.1.0")
    p.setFont(F(9)); p.setPen(pri(55))
    p.drawText(x1, H // 2 + 15, "VIKO ASSISTANT")

    p.setFont(F(20, True)); p.setPen(PRI)
    fm = QFontMetrics(p.font())
    titl = "VIKO"
    p.drawText(cx - fm.horizontalAdvance(titl) // 2, H // 2 + 8, titl)

    p.setFont(F(9)); p.setPen(pri(70))
    sub = "JUST A RATHER VERY INTELLIGENT SYSTEM"
    fm2 = QFontMetrics(p.font())
    p.drawText(cx - fm2.horizontalAdvance(sub) // 2, H // 2 + 23, sub)

    p.setFont(F(14, True)); p.setPen(AMB)
    clk = time.strftime("%H:%M:%S")
    fm3 = QFontMetrics(p.font())
    p.drawText(x2 - fm3.horizontalAdvance(clk), H // 2 + 7, clk)

    p.setFont(F(9)); p.setPen(DIM)
    dat = time.strftime("%a  %d %b %Y")
    fm4 = QFontMetrics(p.font())
    p.drawText(x2 - fm4.horizontalAdvance(dat), H // 2 + 23, dat)


def _ftr_draw(p: QPainter, W: int, H: int, tick: int, state: dict = {}):
    pw    = int(W * 0.50)
    px    = (W - pw) // 2
    slant = 30
    x1    = px + slant + 10
    x2    = px + pw - slant - 10
    cx    = W // 2
    cy    = H // 2 + 6

    p.setFont(F(9)); p.setPen(pri(100))
    p.drawText(x1, cy - 3, "[F4] Mute  ·  [F11] Fullscreen")

    ma = int(150 + 105 * abs(math.sin(tick * 0.14)))
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(suc(ma)))
    p.drawEllipse(QPointF(x1 + 2, cy + 12), 4, 4)
    p.setFont(F(9)); p.setPen(suc(160))
    p.drawText(x1 + 12, cy + 17, "MIC ACTIVE")

    p.setFont(F(10, True)); p.setPen(pri(90))
    brand = "VIKO  ·  B.0.1.0  ·  CLASSIFIED"
    fm = QFontMetrics(p.font())
    p.drawText(cx - fm.horizontalAdvance(brand) // 2, cy + 8, brand)

    p.setFont(F(9)); p.setPen(pri(65))
    copy = "© VIKO INDUSTRIES"
    fm2 = QFontMetrics(p.font())
    p.drawText(x2 - fm2.horizontalAdvance(copy), cy + 8, copy)


class MetricCard(QWidget):
    def __init__(self, label: str, val_fn, color=None, parent=None):
        super().__init__(parent)
        self._label  = label
        self._val_fn = val_fn   # () -> (float 0..1, str)
        self._col    = color or PRI
        self._tick   = 0
        self.setFixedHeight(90)
        t = QTimer(self); t.timeout.connect(self._step); t.start(60)

    def _step(self): self._tick += 1; self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        val, text = self._val_fn()
        p.setPen(QPen(_c(0, 212, 255, 28), 1))
        p.setBrush(QBrush(_c(8, 19, 34, 215)))
        p.drawRoundedRect(QRectF(2, 2, W - 4, H - 4), 7, 7)

        r = 25; acx = 38; acy = H // 2
        rect = QRectF(acx - r, acy - r, r * 2, r * 2)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(pri(26), 2.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(rect, int(210 * 16), int(-240 * 16))
        cg = QConicalGradient(QPointF(acx, acy), 150)
        cg.setColorAt(0, self._col); cg.setColorAt(1, _c(0, 212, 255, 55))
        p.setPen(QPen(QBrush(cg), 2.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(rect, int(210 * 16), int(-240 * val * 16))

        p.setFont(F(11, True)); p.setPen(self._col)
        fm = QFontMetrics(p.font())
        p.drawText(acx - fm.horizontalAdvance(text) // 2, acy + 6, text)

        p.setFont(F(9)); p.setPen(DIM)
        p.drawText(acx + r + 10, acy - 10, self._label)

        bx = acx + r + 10; by = acy + 6; bw = W - bx - 10; bh = 4
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(pri(20)))
        p.drawRoundedRect(QRectF(bx, by, bw, bh), 2, 2)
        lg = QLinearGradient(bx, 0, bx + bw, 0)
        lg.setColorAt(0, pri(135)); lg.setColorAt(1, self._col)
        p.setBrush(QBrush(lg))
        p.drawRoundedRect(QRectF(bx, by, bw * val, bh), 2, 2)
        p.end()


class SystemStatusCard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tick   = 0
        self._online = True
        self._paused = False
        self.setFixedHeight(70)
        t = QTimer(self); t.timeout.connect(self._step); t.start(60)

    def set_online(self, online: bool):
        self._online = online; self.update()

    def set_paused(self, paused: bool):
        self._paused = paused; self.update()

    def _step(self): self._tick += 1; self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        p.setPen(QPen(pri(28), 1))
        p.setBrush(QBrush(_c(8, 19, 34, 215)))
        p.drawRoundedRect(QRectF(2, 2, W - 4, H - 4), 7, 7)

        p.setFont(F(9)); p.setPen(DIM)
        p.drawText(10, 17, "SYSTEM STATUS")

        if self._paused:
            col_fn = amb; lbl_txt = "PAUSED"
        elif self._online:
            col_fn = suc; lbl_txt = "ONLINE"
        else:
            col_fn = lambda a=255: _c(255, 68, 68, a); lbl_txt = "OFFLINE"

        da = int(210 + 45 * math.sin(self._tick * 0.10))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(col_fn(da)))
        p.drawEllipse(QRectF(10, 26, 11, 11))
        pr_r = 8 + 3 * math.sin(self._tick * 0.10)
        pa   = int(80 + 60 * abs(math.sin(self._tick * 0.10)))
        p.setPen(QPen(col_fn(pa), 0.8)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(15.5, 31.5), pr_r, pr_r)

        p.setFont(F(13, True)); p.setPen(col_fn())
        p.drawText(28, 41, lbl_txt)

        p.setFont(F(9)); p.setPen(pri(110))
        p.drawText(10, H - 8, "B.0.1.0")
        p.setFont(F(9)); p.setPen(pri(65))
        p.drawText(W // 2, H - 8, "GEMINI API")
        p.end()


class WorldMapWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tick          = 0
        self._loc_lon       = 101.69
        self._loc_lat       = 3.14
        self._loc_label     = "03°08′N  101°42′E"
        self._country_polys = []
        self._bbox          = None   # (lon_min, lon_max, lat_min, lat_max) when zoomed
        self.setFixedHeight(116)
        t = QTimer(self); t.timeout.connect(self._step); t.start(50)

    def set_location(self, lat: float, lon: float, label: str):
        self._loc_lat = lat; self._loc_lon = lon; self._loc_label = label
        self.update()

    def set_country_polys(self, polys: list):
        """polys: list of rings, each ring = list of (lon, lat) tuples"""
        self._country_polys = polys
        if polys:
            all_pts = [pt for ring in polys for pt in ring]
            lons = [p[0] for p in all_pts]
            lats = [p[1] for p in all_pts]
            span_lon = max(lons) - min(lons)
            span_lat = max(lats) - min(lats)
            pad_lon  = max(2.5, span_lon * 0.14)
            pad_lat  = max(2.5, span_lat * 0.14)
            self._bbox = (
                min(lons) - pad_lon, max(lons) + pad_lon,
                min(lats) - pad_lat, max(lats) + pad_lat,
            )
        else:
            self._bbox = None
        self.update()

    def _step(self): self._tick += 1; self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        lbl_h = 13; mx = 2; my = lbl_h; mh = H - my - 10

        zoomed = self._bbox is not None
        if zoomed:
            lon0, lon1, lat0, lat1 = self._bbox
        else:
            lon0, lon1, lat0, lat1 = -180.0, 180.0, -90.0, 90.0

        def proj(lon, lat):
            x = mx + (lon - lon0) / (lon1 - lon0) * (W - 2 * mx)
            y = my + (lat1 - lat) / (lat1 - lat0) * mh
            return QPointF(x, y)

        if zoomed:
            # Zoomed view: fine grid inside bbox
            span_lon = lon1 - lon0
            span_lat = lat1 - lat0
            step = 10.0 if max(span_lon, span_lat) > 30 else (5.0 if max(span_lon, span_lat) > 10 else 2.0)
            p.setPen(QPen(pri(12), 0.5))
            glon = math.floor(lon0 / step) * step
            while glon <= lon1:
                p.drawLine(proj(glon, lat0), proj(glon, lat1))
                glon += step
            glat = math.floor(lat0 / step) * step
            while glat <= lat1:
                p.drawLine(proj(lon0, glat), proj(lon1, glat))
                glat += step
            if lat0 <= 0 <= lat1:
                p.setPen(QPen(pri(28), 0.7, Qt.PenStyle.DashLine))
                p.drawLine(proj(lon0, 0), proj(lon1, 0))

            # Country polygons filled prominently
            for ring in self._country_polys:
                path = QPainterPath()
                for i, (lon, lat) in enumerate(ring):
                    pt = proj(lon, lat)
                    if i == 0: path.moveTo(pt)
                    else:       path.lineTo(pt)
                path.closeSubpath()
                p.setBrush(QBrush(pri(38))); p.setPen(QPen(PRI, 1.1))
                p.drawPath(path)
        else:
            # World view: continent outlines + grid
            p.setPen(QPen(pri(10), 0.5))
            for lon in range(-180, 181, 45):
                p.drawLine(proj(lon, 90), proj(lon, -90))
            for lat in range(-60, 61, 30):
                p.drawLine(proj(-180, lat), proj(180, lat))
            p.setPen(QPen(pri(20), 0.6, Qt.PenStyle.DashLine))
            p.drawLine(proj(-180, 0), proj(180, 0))
            for poly in _WORLD_POLYS:
                path = QPainterPath()
                for i, (lon, lat) in enumerate(poly):
                    pt = proj(lon, lat)
                    if i == 0: path.moveTo(pt)
                    else:       path.lineTo(pt)
                path.closeSubpath()
                p.setBrush(QBrush(pri(12))); p.setPen(QPen(pri(50), 0.7))
                p.drawPath(path)

        # Location dot (pulsing)
        dot = proj(self._loc_lon, self._loc_lat)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(AMB))
        p.drawEllipse(dot, 3.2, 3.2)
        pr_r = 5.5 + 3.5 * math.sin(self._tick * 0.13)
        pa   = int(160 + 80 * math.sin(self._tick * 0.13))
        p.setPen(QPen(amb(pa // 2), 0.9)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(dot, pr_r, pr_r)

        p.setFont(F(9)); p.setPen(DIM)
        p.drawText(0, 12, "LOCATION  TRACKING")
        p.setFont(F(9)); p.setPen(amb(175))
        p.drawText(0, H - 1, self._loc_label)
        p.end()


def _shorten_model(name: str) -> str:
    """nvidia/nemotron-3-super-120b:free → nemotron-120b"""
    if not name:
        return ""
    short = name.split("/")[-1].replace(":free", "").replace(":nitro", "")
    # Trim long names
    if len(short) > 24:
        short = short[:22] + "…"
    return short.upper()


class CommsCard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tick = 0
        self._latency_ms = 180
        self._gemini_online = False
        self.setFixedHeight(140)
        t = QTimer(self); t.timeout.connect(self._step); t.start(60)

    def set_latency(self, ms: int): self._latency_ms = ms; self.update()
    def set_gemini_online(self, online: bool): self._gemini_online = online; self.update()

    def _step(self): self._tick += 1; self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        p.setPen(QPen(pri(28), 1)); p.setBrush(QBrush(_c(8, 19, 34, 215)))
        p.drawRoundedRect(QRectF(2, 2, W - 4, H - 4), 7, 7)

        # Header
        p.setFont(F(9)); p.setPen(DIM)
        p.drawText(10, 17, "COMMS  ·  GEMINI API")

        # Gemini online dot + label
        import viko.core.client as _cm
        model_name = _shorten_model(_cm.active_model)
        if self._gemini_online:
            da = int(210 + 45 * math.sin(self._tick * 0.10))
            dot_col = suc(da); lbl_col = SUC; lbl_text = "ONLINE"
        else:
            dot_col = _c(255, 68, 68, 220); lbl_col = _c(255, 68, 68); lbl_text = "OFFLINE"
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(dot_col))
        p.drawEllipse(QRectF(10, 27, 9, 9))
        p.setFont(F(13, True)); p.setPen(lbl_col)
        p.drawText(25, 40, lbl_text)

        # Active model name
        p.setFont(F(8)); p.setPen(DIM)
        p.drawText(10, 53, model_name if model_name else "—")

        # Separator
        p.setPen(QPen(pri(25), 1))
        p.drawLine(10, 62, W - 10, 62)

        # Anthropic / Claude indicator
        claude_active = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
        if claude_active:
            ca = int(190 + 55 * math.sin(self._tick * 0.07))
            dot_color = amb(ca)
            lbl_color = AMB
            lbl_text  = "ACTIVE"
        else:
            dot_color = pri(55)
            lbl_color = DIM
            lbl_text  = "INACTIVE"

        p.setFont(F(9)); p.setPen(DIM)
        p.drawText(10, 78, "CLAUDE  ·  ANTHROPIC")
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(dot_color))
        p.drawEllipse(QRectF(10, 85, 8, 8))
        p.setFont(F(10, True)); p.setPen(lbl_color)
        p.drawText(24, 97, lbl_text)

        # Latency bar
        lat = min(1.0, self._latency_ms / 1000)
        p.setFont(F(9)); p.setPen(DIM)
        p.drawText(10, 121, "LATENCY")
        bx, by, bw, bh = 68, 113, W - 78, 5
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(pri(20)))
        p.drawRoundedRect(QRectF(bx, by, bw, bh), 2, 2)
        lg = QLinearGradient(bx, 0, bx + bw, 0)
        lg.setColorAt(0, suc(175)); lg.setColorAt(1, pri(115))
        p.setBrush(QBrush(lg))
        p.drawRoundedRect(QRectF(bx, by, bw * lat, bh), 2, 2)
        p.setFont(F(9)); p.setPen(suc(175))
        p.drawText(int(bx + bw * lat) + 4, 121, f"{self._latency_ms}ms")
        p.end()


class SessionCard(QWidget):
    _t0 = time.time()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tick = 0
        self._ops  = 0   # updated via inc_ops()
        self.setFixedHeight(74)
        t = QTimer(self); t.timeout.connect(self._step); t.start(1000)

    def inc_ops(self): self._ops += 1; self.update()

    def _step(self): self._tick += 1; self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        p.setPen(QPen(pri(28), 1)); p.setBrush(QBrush(_c(8, 19, 34, 215)))
        p.drawRoundedRect(QRectF(2, 2, W - 4, H - 4), 7, 7)

        e = int(time.time() - self._t0)
        ts = f"{e // 3600:02d}:{(e % 3600) // 60:02d}:{e % 60:02d}"

        p.setFont(F(9)); p.setPen(DIM)
        p.drawText(10, 17, "SESSION INTEL")
        p.setFont(F(14, True)); p.setPen(AMB)
        p.drawText(10, 45, ts)
        p.setFont(F(9)); p.setPen(pri(135))
        p.drawText(10, H - 8, "UPTIME")
        p.drawText(W // 2, H - 8, f"OPS: {self._ops}")
        p.end()


class HudCanvas(QWidget):
    """Concentric segmented rings, scanner arcs, pulse waves, waveform, state indicator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tick   = 0
        self._audio  = 0.0
        self._rot    = [0.0] * 7
        self._spd    = [0.28, -0.44, 0.20, -0.36, 0.52, -0.22, 0.12]
        self._pulses: list[float] = [0.0, 80.0, 160.0]
        self._scan     = [0.0, 180.0, 90.0, 270.0]
        self._scan_spd = [1.4, -0.9, 2.1, -1.6]
        self.state       = "idle"      # "idle" | "listening" | "speaking" | "thinking"
        self._muted      = False
        self._blink      = True
        self._blink_tick = 0
        import random as _rnd
        self._rnd = _rnd
        N = 48
        self._wave = [0.0] * N
        self.setMinimumSize(320, 320)
        t = QTimer(self); t.timeout.connect(self._step); t.start(40)

    def set_state(self, state: str):
        """Accept viko.py state strings and map to animation state."""
        s = state.upper()
        if s == "SPEAKING":     self.state = "speaking"
        elif s == "LISTENING":  self.state = "listening"
        elif s == "THINKING":   self.state = "listening"
        elif s == "WORKING":    self.state = "working"
        elif s == "CODING":     self.state = "coding"
        elif s == "MUTED":      self._muted = True; self.state = "idle"
        elif s == "PAUSED":     self.state = "paused"
        elif s == "OFFLINE":    self.state = "idle"
        else:                   self.state = "idle"
        if s != "MUTED":        self._muted = False

    def set_audio_level(self, rms: float):
        """Feed real RMS (0..1) from mic callback; falls back to simulated."""
        self._audio = min(1.0, rms * 3)

    def _step(self):
        self._tick += 1
        self._blink_tick += 1
        if self._blink_tick % 14 == 0:
            self._blink = not self._blink

        if self.state == "paused":
            # drain waveform to flat; freeze all other animations
            for i in range(len(self._wave)):
                self._wave[i] += (0.01 - self._wave[i]) * 0.1
            self.update()
            return

        if self._audio < 0.01:
            self._audio = 0.30 + 0.28 * abs(math.sin(self._tick * 0.07))
        for i in range(7):
            self._rot[i] = (self._rot[i] + self._spd[i]) % 360
        lim = 210.0
        spd = 1.8 + self._audio * 0.8
        self._pulses = [r + spd for r in self._pulses if r + spd < lim]
        if len(self._pulses) < 4 and self._tick % 38 == 0:
            self._pulses.append(0.0)
        for i in range(4):
            self._scan[i] = (self._scan[i] + self._scan_spd[i]) % 360
        for i in range(len(self._wave)):
            if self.state == "speaking":
                tgt = self._rnd.uniform(0.12, 1.0)
            elif self.state == "listening":
                tgt = 0.04 + 0.18 * abs(math.sin(self._tick * 0.09 + i * 0.55))
            else:
                tgt = 0.02 + 0.03 * abs(math.sin(self._tick * 0.04 + i * 0.3))
            self._wave[i] += (tgt - self._wave[i]) * 0.25
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        cx = W // 2 + (RIGHT_W - LEFT_W) // 2
        cy = H // 2
        s  = min(W, H) / 620.0   # scale relative to reference canvas

        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(BG))
        p.drawRect(0, 0, W, H)
        rg = QRadialGradient(QPointF(cx, cy), min(W, H) // 2)
        rg.setColorAt(0, _c(0, 45, 75, 28)); rg.setColorAt(1, _c(0, 0, 0, 0))
        p.setBrush(QBrush(rg)); p.drawRect(0, 0, W, H)

        rings = [
            (172, 48,  3, 0.9, 28, False),
            (154, 12,  8, 2.2, 55, True ),
            (136, 64,  2, 0.8, 26, False),
            (118, 24,  5, 1.5, 44, False),
            (100,  8,  8, 2.8, 80, True ),
            ( 82, 40,  4, 1.0, 38, False),
            ( 64, 16,  6, 2.2, 68, True ),
        ]
        for i, (r, nseg, gap, lw, base_a, prom) in enumerate(rings):
            r = int(r * s)
            rot = self._rot[i]; seg_deg = 360 / nseg; arc_deg = seg_deg - gap
            ab = int(self._audio * 38) if prom else 0
            a  = min(255, base_a + ab)
            rect = QRectF(cx - r, cy - r, r * 2, r * 2)
            if prom:
                p.setPen(QPen(pri(a // 5), lw * 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
                for j in range(nseg):
                    p.drawArc(rect, int((rot + j * seg_deg) * 16), int(arc_deg * 16))
            p.setPen(QPen(pri(a), lw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
            for j in range(nseg):
                p.drawArc(rect, int((rot + j * seg_deg) * 16), int(arc_deg * 16))

        lim = 210.0
        for pr in self._pulses:
            a = max(0, int(200 * (1.0 - pr / lim)))
            p.setPen(QPen(pri(a), 1.2)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), pr * s, pr * s)

        t_r_out = 174.0 * s; t_r_in = t_r_out - 7 * s; t_r_lng = t_r_out - 13 * s
        p.setPen(QPen(pri(90), 1))
        for deg in range(0, 360, 6):
            rad = math.radians(deg); cos_r, sin_r = math.cos(rad), math.sin(rad)
            inn = t_r_lng if deg % 30 == 0 else t_r_in
            p.drawLine(QPointF(cx + t_r_out * cos_r, cy - t_r_out * sin_r),
                       QPointF(cx + inn * cos_r, cy - inn * sin_r))
        m_r_out = 102.0 * s; p.setPen(QPen(pri(70), 1))
        for deg in range(0, 360, 15):
            rad = math.radians(deg); cos_r, sin_r = math.cos(rad), math.sin(rad)
            inn = m_r_out - 10 * s if deg % 45 == 0 else m_r_out - 5 * s
            p.drawLine(QPointF(cx + m_r_out * cos_r, cy - m_r_out * sin_r),
                       QPointF(cx + inn * cos_r, cy - inn * sin_r))

        scanners = [(174,0,38,2.2,pri),(174,1,22,1.5,pri),(136,2,52,1.8,amb),(154,3,28,1.2,pri)]
        sa = int(160 + 60 * self._audio)
        for r, si, arc_len, lw, col_fn in scanners:
            r = int(r * s)
            rect = QRectF(cx - r, cy - r, r * 2, r * 2)
            p.setPen(QPen(col_fn(sa // 5), lw * 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
            p.drawArc(rect, int(self._scan[si] * 16), int(arc_len * 16))
            p.setPen(QPen(col_fn(sa), lw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
            p.drawArc(rect, int(self._scan[si] * 16), int(arc_len * 16))

        card_r = 100 * s
        for angle, lbl in [(90,"N"),(0,"E"),(270,"S"),(180,"W")]:
            a_rad = math.radians(angle)
            mx2 = cx + int(card_r * math.cos(a_rad)); my2 = cy - int(card_r * math.sin(a_rad))
            p.setPen(QPen(pri(115), 1)); p.setBrush(QBrush(pri(28)))
            p.drawEllipse(QPointF(mx2, my2), 5.5 * s, 5.5 * s)
            p.setFont(F(9, True)); p.setPen(pri(185))
            p.drawText(mx2 - 3, my2 + 4, lbl)

        orb_r = (38 + self._audio * 10) * s
        rg2 = QRadialGradient(QPointF(cx, cy), orb_r)
        rg2.setColorAt(0.00, pri(210)); rg2.setColorAt(0.35, pri(70))
        rg2.setColorAt(0.75, pri(14)); rg2.setColorAt(1.00, pri(0))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(rg2))
        p.drawEllipse(QPointF(cx, cy), orb_r, orb_r)
        p.setPen(QPen(pri(155), 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), 19 * s, 19 * s)
        for i in range(4):
            wr = (21 + i * 9 + self._audio * 15) * s; wa = max(0, int(125 - i * 28))
            p.setPen(QPen(pri(wa), 1)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), wr, wr)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(PRI))
        p.drawEllipse(QPointF(cx, cy), max(2.0, 3 * s), max(2.0, 3 * s))

        N = len(self._wave); bw = max(5, int(9 * s)); max_h = int(55 * s)
        wx0 = cx - N * bw // 2; wy = H - 24
        for i, h_frac in enumerate(self._wave):
            hgt = max(2, int(h_frac * max_h))
            if self.state == "speaking":    col = PRI if h_frac > 0.55 else pri(110)
            elif self.state == "listening": col = pri(130)
            elif self.state == "working":   col = amb(180) if h_frac > 0.3 else amb(90)
            elif self.state == "coding":    col = PRI if h_frac > 0.4 else pri(160)
            else:                           col = pri(50)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(col))
            p.drawRect(QRectF(wx0 + i * bw, wy - hgt, bw - 1, hgt))
        p.setPen(QPen(pri(35), 1))
        p.drawLine(int(wx0), wy, int(wx0 + N * bw), wy)

        if self.state == "speaking":    dot_col = AMB; lbl_text = "SPEAKING"
        elif self.state == "listening": dot_col = SUC; lbl_text = "LISTENING"
        elif self.state == "working":   dot_col = amb(int(180 + 60 * math.sin(self._tick * 0.12))); lbl_text = "WORKING"
        elif self.state == "coding":    dot_col = PRI; lbl_text = "CODING"
        elif self.state == "paused":    dot_col = AMB; lbl_text = "PAUSED"
        else:                           dot_col = pri(55); lbl_text = "STANDBY"
        if self._muted: dot_col = _c(255, 68, 68); lbl_text = "MUTED"

        sym = "●" if self._blink else "○"
        ind_y = wy - max_h - 20
        p.setFont(F(12, True)); p.setPen(dot_col)
        lbl_full = f"{sym}  {lbl_text}"
        fm = QFontMetrics(p.font())
        p.drawText(cx - fm.horizontalAdvance(lbl_full) // 2, ind_y, lbl_full)

        p.setFont(F(9)); p.setPen(pri(75))
        top_lbl = "SYSTEM TRACKING"
        fm2 = QFontMetrics(p.font())
        p.drawText(cx - fm2.horizontalAdvance(top_lbl) // 2, cy - int(185 * s), top_lbl)
        p.end()


class LogWidget(QTextEdit):
    """Activity log with typewriter effect. Thread-safe via signal."""
    _sig = pyqtSignal(str)

    # Tag colour map (matches ui_backup.py pattern)
    _TAG_COLORS = {
        "you":  "#ffb347",
        "ai":   "#00d4ff",
        "err":  "#ff4444",
        "file": "#00ff9f",
        "sys":  "#3a8a9a",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Courier New", 12))
        self.setStyleSheet("""
            QTextEdit {
                background: rgba(8,19,34,215);
                color: rgba(200,232,248,175);
                border: 1px solid rgba(0,212,255,28);
                border-radius: 7px;
                padding: 8px;
            }
            QScrollBar:vertical { width: 5px; background: rgba(0,0,0,0); }
            QScrollBar::handle:vertical { background: rgba(0,212,255,60); border-radius: 2px; }
        """)
        self._queue: list[str] = []
        self._typing = False
        self._text   = ""
        self._pos    = 0
        self._tag    = "sys"
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._sig.connect(self._enqueue)

    def append_log(self, text: str):
        self._sig.emit(text)

    def _enqueue(self, text: str):
        self._queue.append(text)
        if not self._typing:
            self._next()

    def _next(self):
        if not self._queue:
            self._typing = False; return
        self._typing = True
        raw = self._queue.pop(0)
        # detect tag prefix like "YOU: " "AI: " "SYS: " "ERR: " "FILE: "
        low = raw.lower()
        for tag in ("you", "ai", "err", "file", "sys"):
            if low.startswith(tag + ":") or low.startswith(f"[{tag}]"):
                self._tag = tag; break
        else:
            self._tag = "sys"
        from datetime import datetime
        self._text = f"{datetime.now():%H:%M} {raw}"; self._pos = 0
        self._tmr.start(6)

    def _step(self):
        if self._pos >= len(self._text):
            self._tmr.stop()
            self.append("")   # newline
            self._next(); return
        chunk = self._text[self._pos: self._pos + 3]
        col   = self._TAG_COLORS.get(self._tag, "#3a8a9a")
        self.moveCursor(self.textCursor().MoveOperation.End)
        self.setTextColor(QColor(col))
        self.insertPlainText(chunk)
        self.moveCursor(self.textCursor().MoveOperation.End)
        self._pos += 3


class FileDropCard(QWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hover   = False
        self._tick    = 0
        self._current = None
        self.setFixedHeight(80)
        self.setAcceptDrops(True)
        t = QTimer(self); t.timeout.connect(self._step); t.start(60)

    def current_file(self) -> str | None: return self._current
    def _step(self): self._tick += 1; self.update()
    def enterEvent(self, _): self._hover = True;  self.update()
    def leaveEvent(self, _): self._hover = False; self.update()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
    def dropEvent(self, e):
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self._current = path
            self.file_selected.emit(path)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        alpha = int(45 + 30 * math.sin(self._tick * 0.1)) if not self._hover else 90
        p.setPen(QPen(pri(alpha), 1, Qt.PenStyle.DashLine))
        p.setBrush(QBrush(_c(0, 212, 255, 8 if not self._hover else 18)))
        p.drawRoundedRect(QRectF(2, 2, W - 4, H - 4), 7, 7)
        p.setFont(F(10)); p.setPen(pri(alpha + 40))
        lbl = "⬡  DROP FILE HERE"
        fm  = QFontMetrics(p.font())
        p.drawText((W - fm.horizontalAdvance(lbl)) // 2, H // 2 + 3, lbl)
        p.setFont(F(9)); p.setPen(DIM)
        sub = "or click to browse"
        fm2 = QFontMetrics(p.font())
        p.drawText((W - fm2.horizontalAdvance(sub)) // 2, H // 2 + 20, sub)
        p.end()

    def mousePressEvent(self, _):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Select file")
        if path:
            self._current = path; self.file_selected.emit(path)


class LeftPanel(QWidget):
    def __init__(self, metrics_snapshot_fn, parent=None):
        """
        metrics_snapshot_fn: callable () -> dict with keys cpu, mem, disk, net
        Values are floats 0..1.
        """
        super().__init__(parent)
        self.setFixedWidth(LEFT_W)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(5)

        self._status_card = SystemStatusCard()
        self._map         = WorldMapWidget()

        def _metric(key, scale=100):
            def fn():
                v = metrics_snapshot_fn().get(key, 0.0)
                return v, f"{int(v * scale)}%"
            return fn

        lay.addWidget(self._map)
        lay.addWidget(self._status_card)
        lay.addWidget(MetricCard("CORE PROC", _metric("cpu"),  PRI))
        lay.addWidget(MetricCard("MEM ARRAY", _metric("mem"),  AMB))
        lay.addWidget(MetricCard("STORAGE",   _metric("disk"), SUC))
        lay.addStretch()

    def set_online(self, online: bool):
        self._status_card.set_online(online)

    def set_paused(self, paused: bool):
        self._status_card.set_paused(paused)

    def set_location(self, lat: float, lon: float, label: str):
        self._map.set_location(lat, lon, label)

    def set_country_polys(self, polys: list):
        self._map.set_country_polys(polys)


class RightMetricsPanel(QWidget):
    def __init__(self, metrics_snapshot_fn, parent=None):
        super().__init__(parent)
        self.setFixedWidth(RIGHT_W)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(5)

        def net_fn():
            v = metrics_snapshot_fn().get("net", 0.0)
            return v, f"{int(v * 999)}K"

        self._comms = CommsCard()
        self._sess  = SessionCard()
        lay.addWidget(MetricCard("COMMS BW", net_fn, pri(220)))
        lay.addWidget(self._comms)
        lay.addWidget(self._sess)
        lay.addStretch()

    def inc_ops(self): self._sess.inc_ops()

    def set_latency(self, ms: int): self._comms.set_latency(ms)
    def set_gemini_online(self, online: bool): self._comms.set_gemini_online(online)


class ActivityPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(RIGHT_W)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(8)

        lbl_log = QLabel("◈  ACTIVITY LOG")
        lbl_log.setFont(F(11, True))
        lbl_log.setStyleSheet(f"color: {PRI.name()};")
        lay.addWidget(lbl_log)

        self._log = LogWidget()
        lay.addWidget(self._log, 1)

        lbl_file = QLabel("⬡  FILE UPLOAD")
        lbl_file.setFont(F(11, True))
        lbl_file.setStyleSheet(f"color: {AMB.name()};")
        lay.addWidget(lbl_file)

        self._drop = FileDropCard()
        lay.addWidget(self._drop)

        lbl_chat = QLabel("◎  COMMAND INPUT")
        lbl_chat.setFont(F(11, True))
        lbl_chat.setStyleSheet(f"color: {PRI.name()};")
        lay.addWidget(lbl_chat)

        row = QWidget(); ilay = QHBoxLayout(row)
        ilay.setContentsMargins(0, 0, 0, 0); ilay.setSpacing(6)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a command...")
        self._input.setFont(F(11))
        self._input.setStyleSheet("""
            QLineEdit {
                background: rgba(8,19,34,215); color: rgba(200,232,248,200);
                border: 1px solid rgba(0,212,255,50); border-radius: 6px; padding: 6px 8px;
            }
            QLineEdit:focus { border-color: rgba(0,212,255,140); }
        """)
        ilay.addWidget(self._input, 1)
        self._send_btn = QPushButton("▶")
        self._send_btn.setFixedSize(34, 34); self._send_btn.setFont(F(10, True))
        self._send_btn.setStyleSheet(f"""
            QPushButton {{ background: rgba(0,212,255,25); color: {PRI.name()};
                border: 1px solid rgba(0,212,255,80); border-radius: 6px; }}
            QPushButton:hover {{ background: rgba(0,212,255,55); }}
        """)
        ilay.addWidget(self._send_btn)
        lay.addWidget(row)

        # Wire send signals NOW (main thread) — callback set later via setter
        self._cmd_cb = None
        import threading as _t

        def _send():
            text = self._input.text().strip()
            if not text or not self._cmd_cb:
                return
            self._input.clear()
            _t.Thread(target=self._cmd_cb, args=(text,), daemon=True).start()

        self._input.returnPressed.connect(_send)
        self._send_btn.clicked.connect(lambda _=False: _send())

    def append_log(self, text: str): self._log.append_log(text)
    def current_file(self) -> str | None: return self._drop.current_file()

    def on_text_command_changed(self, cb):
        # Safe to call from any thread — just stores the callback
        self._cmd_cb = cb

    def set_paused(self, paused: bool):
        self._input.setEnabled(not paused)
        self._send_btn.setEnabled(not paused)
        self._input.setPlaceholderText("[ PAUSED — press START to resume ]" if paused else "Type a command...")


class BootScreen(QWidget):
    """Full-window boot overlay: HUD rings + centered progress bar + status label."""

    finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pct   = 0.0
        self._label = "INITIALIZING..."
        self._tick  = 0
        self._rot   = [0.0] * 7
        self._spd   = [0.28, -0.44, 0.20, -0.36, 0.52, -0.22, 0.12]
        self._alpha = 255          # for fade-out
        self._fading = False

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(40)

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

    def set_progress(self, pct: float, label: str) -> None:
        self._pct   = max(0.0, min(1.0, pct))
        self._label = label.upper()
        if self._pct >= 1.0 and not self._fading:
            self._fading = True
        self.update()

    def _step(self):
        self._tick += 1
        for i in range(7):
            self._rot[i] = (self._rot[i] + self._spd[i]) % 360
        if self._fading:
            self._alpha = max(0, self._alpha - 12)
            if self._alpha == 0:
                self._timer.stop()
                self.finished.emit()
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        cx, cy = W // 2, H // 2
        s = min(W, H) / 620.0

        # Background
        p.setOpacity(self._alpha / 255)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(BG))
        p.drawRect(0, 0, W, H)

        rg = QRadialGradient(QPointF(cx, cy), min(W, H) // 2)
        rg.setColorAt(0, _c(0, 45, 75, 30))
        rg.setColorAt(1, _c(0, 0, 0, 0))
        p.setBrush(QBrush(rg))
        p.drawRect(0, 0, W, H)

        # Concentric rings (same as HudCanvas)
        rings = [
            (172, 48,  3, 0.9, 28, False),
            (154, 12,  8, 2.2, 55, True ),
            (136, 64,  2, 0.8, 26, False),
            (118, 24,  5, 1.5, 44, False),
            (100,  8,  8, 2.8, 80, True ),
            ( 82, 40,  4, 1.0, 38, False),
            ( 64, 16,  6, 2.2, 68, True ),
        ]
        for i, (r, nseg, gap, lw, base_a, prom) in enumerate(rings):
            r = int(r * s)
            rot = self._rot[i]; seg_deg = 360 / nseg; arc_deg = seg_deg - gap
            a = min(255, base_a)
            rect = QRectF(cx - r, cy - r, r * 2, r * 2)
            if prom:
                p.setPen(QPen(pri(a // 5), lw * 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
                for j in range(nseg):
                    p.drawArc(rect, int((rot + j * seg_deg) * 16), int(arc_deg * 16))
            p.setPen(QPen(pri(a), lw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
            for j in range(nseg):
                p.drawArc(rect, int((rot + j * seg_deg) * 16), int(arc_deg * 16))

        # VIKO label at center
        p.setFont(F(18, True)); p.setPen(pri(200))
        fm = QFontMetrics(p.font())
        lbl_w = fm.horizontalAdvance("VIKO")
        p.drawText(cx - lbl_w // 2, cy - int(18 * s) - 8, "VIKO")

        # Progress bar (thin, centered, ~320px wide)
        bar_w = min(320, int(W * 0.4)); bar_h = 3
        bx = cx - bar_w // 2; by = cy + int(18 * s) + 10
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(pri(20)))
        p.drawRoundedRect(QRectF(bx, by, bar_w, bar_h), 1, 1)
        lg = QLinearGradient(bx, 0, bx + bar_w, 0)
        lg.setColorAt(0, suc(200)); lg.setColorAt(1, pri(180))
        p.setBrush(QBrush(lg))
        p.drawRoundedRect(QRectF(bx, by, bar_w * self._pct, bar_h), 1, 1)

        # Status label below bar
        p.setFont(F(11)); p.setPen(pri(160))
        fm2 = QFontMetrics(p.font())
        sl_w = fm2.horizontalAdvance(self._label)
        p.drawText(cx - sl_w // 2, by + bar_h + 18, self._label)

        p.end()
