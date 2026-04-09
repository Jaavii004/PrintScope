"""
PrintScope UI Components — Premium Design System v3.0
Dark glassmorphism · Custom charts · Micro-animations
"""
from __future__ import annotations
import datetime
from typing import Optional, List

from PyQt6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QTextEdit,
    QHBoxLayout, QVBoxLayout, QGridLayout,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QScrollArea, QStackedWidget, QSizePolicy, QSpacerItem,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QBrush, QLinearGradient,
    QPainterPath, QPolygonF, QFont, QFontDatabase,
)

# ── Design Tokens ─────────────────────────────────────────────────────────────
BG_BASE       = "#0d0d0f"
BG_SURFACE    = "#141416"
BG_CARD       = "#1a1a1e"
BG_HOVER      = "#212128"
BORDER        = "#252530"
BORDER_BRIGHT = "#35354a"

ACCENT        = "#2ed573"      # neon green
ACCENT_BLUE   = "#4f8ef7"
ACCENT_WARN   = "#f39c12"
ACCENT_DANGER = "#e74c3c"
ACCENT_PURPLE = "#a29bfe"

TEXT_PRIMARY   = "#f0f0f5"
TEXT_SECONDARY = "#888899"
TEXT_MUTED     = "#444455"

FONT_MONO = "Consolas, 'Courier New', monospace"
FONT_MAIN = "'Segoe UI', 'SF Pro Display', Arial, sans-serif"


def _hex_to_qcolor(h: str, alpha: int = 255) -> QColor:
    c = QColor(h)
    c.setAlpha(alpha)
    return c


# ── Toner Pill ────────────────────────────────────────────────────────────────

class TonerPill(QWidget):
    """Premium toner level indicator with gradient fill and percentage label."""

    def __init__(self, level: int, max_cap: int, name: str = "", parent=None):
        super().__init__(parent)
        self.level   = max(0, level)
        self.max_cap = max(1, max_cap)
        self.name    = name
        self.pct     = min(100, int(self.level / self.max_cap * 100))

        self.setFixedHeight(18)
        self.setMinimumWidth(90)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        if self.pct < 15:
            self._color = QColor(ACCENT_DANGER)
        elif self.pct < 35:
            self._color = QColor(ACCENT_WARN)
        else:
            self._color = QColor(ACCENT)

        tip = f"{name}: {self.pct}% remaining"
        self.setToolTip(tip)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = h / 2

        # Track background
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(BORDER))
        p.drawRoundedRect(0, 0, w, h, int(r), int(r))

        # Filled portion
        fill_w = max(int(r * 2), int(w * self.pct / 100))
        grad = QLinearGradient(0, 0, fill_w, 0)
        c2 = QColor(self._color)
        c2.setAlpha(180)
        grad.setColorAt(0.0, c2)
        grad.setColorAt(1.0, self._color)
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(0, 0, fill_w, h, int(r), int(r))

        # Percentage text
        p.setPen(QColor(TEXT_PRIMARY))
        f = QFont(FONT_MAIN, 7)
        f.setWeight(QFont.Weight.Bold)
        p.setFont(f)
        label = f"{self.pct}%"
        p.drawText(0, 0, w, h, Qt.AlignmentFlag.AlignCenter, label)


# ── Stat Card ─────────────────────────────────────────────────────────────────

class StatCard(QFrame):
    """Glassmorphism KPI card."""

    def __init__(self, title: str, icon: str, color: str = ACCENT_BLUE, parent=None):
        super().__init__(parent)
        self._color = color
        self.setObjectName("stat_card")
        self.setFixedHeight(90)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(8)

        self._icon = QLabel(icon)
        self._icon.setStyleSheet(f"color: {color}; font-size: 18px;")
        top.addWidget(self._icon)

        self._title = QLabel(title)
        self._title.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 10px; font-weight: 600; letter-spacing: 1px;"
        )
        top.addWidget(self._title)
        top.addStretch()
        layout.addLayout(top)

        self._value = QLabel("—")
        self._value.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 26px; font-weight: 800; letter-spacing: -1px;"
        )
        layout.addWidget(self._value)

        self._apply_style(False)

    def _apply_style(self, hovered: bool):
        bg = BG_HOVER if hovered else BG_CARD
        border = self._color if hovered else BORDER
        self.setStyleSheet(f"""
            QFrame#stat_card {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 10px;
            }}
        """)

    def enterEvent(self, e):  self._apply_style(True)
    def leaveEvent(self, e):  self._apply_style(False)

    def set_value(self, v):   self._value.setText(str(v))


# ── Usage Trend Chart ─────────────────────────────────────────────────────────

class UsageTrendChart(QWidget):
    """Custom-painted line chart with area gradient fill."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(110)
        self._data: List[tuple] = []   # (timestamp, level 0-100)
        self._color = QColor(ACCENT)
        self.setToolTip("Historical toner consumption")

    def set_data(self, history: List[tuple], color: str = ACCENT):
        self._data = history[-30:]
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        p.setPen(QPen(QColor(BORDER), 1))
        p.setBrush(QColor(BG_SURFACE))
        p.drawRoundedRect(0, 0, w, h, 8, 8)

        if len(self._data) < 2:
            p.setPen(QColor(TEXT_MUTED))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Collecting data…")
            return

        pad = 10
        usable_w = w - pad * 2
        usable_h = h - pad * 2

        # Horizontal grid lines
        p.setPen(QPen(QColor(BORDER_BRIGHT), 1, Qt.PenStyle.DotLine))
        for pct in (25, 50, 75):
            y = int(pad + usable_h * (1 - pct / 100))
            p.drawLine(pad, y, w - pad, y)

        # Build point list
        pts: List[QPointF] = []
        for i, (_, val) in enumerate(self._data):
            x = pad + usable_w * i / (len(self._data) - 1)
            y = pad + usable_h * (1 - val / 100)
            pts.append(QPointF(x, y))

        # Area fill
        path = QPainterPath()
        path.moveTo(pts[0].x(), h - pad)
        for pt in pts:
            path.lineTo(pt)
        path.lineTo(pts[-1].x(), h - pad)
        path.closeSubpath()

        grad = QLinearGradient(0, 0, 0, h)
        c_top = QColor(self._color)
        c_top.setAlpha(80)
        c_bot = QColor(self._color)
        c_bot.setAlpha(0)
        grad.setColorAt(0.0, c_top)
        grad.setColorAt(1.0, c_bot)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawPath(path)

        # Line
        pen = QPen(self._color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        poly = QPolygonF(pts)
        p.drawPolyline(poly)

        # Dots at each point
        p.setBrush(self._color)
        p.setPen(QPen(QColor(BG_SURFACE), 2))
        for pt in pts:
            p.drawEllipse(pt, 3, 3)

        # Last value badge
        last_val = self._data[-1][1]
        last_pt  = pts[-1]
        p.setPen(QColor(TEXT_PRIMARY))
        f = QFont(FONT_MAIN, 8)
        f.setWeight(QFont.Weight.Bold)
        p.setFont(f)
        p.drawText(int(last_pt.x()) - 16, int(last_pt.y()) - 6, f"{int(last_val)}%")


# ── Detail Sidebar ────────────────────────────────────────────────────────────

class DetailsSidebar(QFrame):
    """Slide-in device intelligence panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("details_sidebar")
        self.setFixedWidth(300)
        self.setStyleSheet(f"""
            QFrame#details_sidebar {{
                background: {BG_SURFACE};
                border-left: 1px solid {BORDER};
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header bar
        header = QFrame()
        header.setStyleSheet(f"background: {BG_CARD}; border-bottom: 1px solid {BORDER};")
        header.setFixedHeight(52)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(20, 0, 12, 0)

        self._hdr_label = QLabel("DEVICE DETAILS")
        self._hdr_label.setStyleSheet(
            f"color: {ACCENT}; font-size: 10px; font-weight: 800; letter-spacing: 2px;"
        )
        h_layout.addWidget(self._hdr_label)
        h_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_SECONDARY};
                border: none;
                font-size: 14px;
                border-radius: 4px;
            }}
            QPushButton:hover {{ background: {BG_HOVER}; color: {TEXT_PRIMARY}; }}
        """)
        close_btn.clicked.connect(self.hide)
        h_layout.addWidget(close_btn)
        root.addWidget(header)

        # Scrollable body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.verticalScrollBar().setStyleSheet(f"""
            QScrollBar:vertical {{ background: {BG_SURFACE}; width: 4px; margin: 0; border-radius: 2px; }}
            QScrollBar::handle:vertical {{ background: {BORDER_BRIGHT}; border-radius: 2px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        self._body_layout = QVBoxLayout(body)
        self._body_layout.setContentsMargins(20, 20, 20, 20)
        self._body_layout.setSpacing(16)

        scroll.setWidget(body)
        root.addWidget(scroll)

        self.hide()

    def _clear(self):
        while self._body_layout.count():
            item = self._body_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _add_section(self, title: str):
        lbl = QLabel(title.upper())
        lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 9px; font-weight: 800; letter-spacing: 2px;"
            f" padding-top: 8px; border-top: 1px solid {BORDER};"
        )
        self._body_layout.addWidget(lbl)

    def _add_row(self, label: str, value: str):
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        rl = QVBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(2)
        lbl = QLabel(label.upper())
        lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9px; font-weight: 600; letter-spacing: 0.8px;")
        val = QLabel(value or "—")
        val.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px;")
        val.setWordWrap(True)
        rl.addWidget(lbl)
        rl.addWidget(val)
        self._body_layout.addWidget(row)

    def _add_toner_section(self, consumables: list):
        self._add_section("SUPPLIES")
        for c in consumables:
            row = QWidget()
            row.setStyleSheet("background: transparent;")
            rl = QVBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(4)
            name_lbl = QLabel(c.get("name", "Supply"))
            name_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px;")
            pill = TonerPill(c.get("level", 0), c.get("max_capacity", 100), c.get("name", ""))
            rl.addWidget(name_lbl)
            rl.addWidget(pill)

            days = c.get("est_days")
            if days is not None and days < 14:
                badge_col = ACCENT_DANGER if days < 5 else ACCENT_WARN
                badge = QLabel(f"⚠ ~{days} days remaining")
                badge.setStyleSheet(
                    f"color: {badge_col}; font-size: 9px; font-weight: 700;"
                )
                rl.addWidget(badge)

            self._body_layout.addWidget(row)

    def update_details(self, p: dict):
        self._clear()

        # Status badge
        is_online = p.get("is_online", False)
        status_col = ACCENT if is_online else ACCENT_DANGER
        badge = QLabel(f"● {p.get('status', 'Unknown')}")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"color: {status_col}; background: {BG_CARD}; border: 1px solid {status_col}33;"
            f" border-radius: 6px; padding: 6px; font-size: 11px; font-weight: 700;"
        )
        self._body_layout.addWidget(badge)

        # Identity
        title = f"{p.get('brand', '')} {p.get('model', 'Unknown Device')}".strip()
        t_lbl = QLabel(title)
        t_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 14px; font-weight: 800;")
        t_lbl.setWordWrap(True)
        self._body_layout.addWidget(t_lbl)

        # Fields
        self._add_section("NETWORK")
        self._add_row("IP Address",  p.get("ip", ""))
        self._add_row("Hostname",    p.get("hostname", ""))
        self._add_row("MAC Address", p.get("mac_address", ""))

        self._add_section("DEVICE")
        self._add_row("Serial Number", p.get("serial_number", ""))
        self._add_row("Location",      p.get("location", ""))
        self._add_row("Uptime",        p.get("uptime", ""))

        self._add_section("INTELLIGENCE")
        fw = p.get("firmware_version")
        self._add_row("Firmware", fw if fw else "Unknown")
        
        pages = p.get("total_pages")
        self._add_row("Life Count", f"{pages:,} pages" if pages else "Unknown")
        
        mem = p.get("memory_mb")
        self._add_row("Memory", f"{mem} MB" if mem else "Unknown")

        # Consumables
        consumables = p.get("consumables", [])
        if consumables:
            self._add_toner_section(consumables)
        else:
            self._add_section("SUPPLIES")
            no_data = QLabel("No toner data available")
            no_data.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; font-style: italic;")
            self._body_layout.addWidget(no_data)

        # Trend chart
        history = p.get("history", [])
        chart_data = []
        for entry in history:
            for c in entry.get("consumables", []):
                chart_data.append((entry.get("timestamp", ""), c.get("level", 0)))
                break

        if len(chart_data) >= 2:
            chart_lbl = QLabel("CONSUMPTION TREND")
            chart_lbl.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 9px; font-weight: 800; letter-spacing: 2px;"
                f" padding-top: 8px; border-top: 1px solid {BORDER};"
            )
            self._body_layout.addWidget(chart_lbl)
            chart = UsageTrendChart()
            chart.set_data(chart_data)
            self._body_layout.addWidget(chart)

        self._body_layout.addStretch()
        self.show()


# ── Printer Table ─────────────────────────────────────────────────────────────

class PrinterTable(QTableWidget):
    """Premium gridless printer inventory table."""

    COLUMNS = ["", "Status", "IP Address", "Hostname", "Brand / Model", "Supplies", "Last Seen"]
    STATUS_COL = 1
    IP_COL     = 2

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)

        hdr = self.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # indicator dot
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)

        self.setColumnWidth(0, 10)   # dot
        self.setColumnWidth(1, 90)   # status
        self.setColumnWidth(2, 120)  # IP
        self.setColumnWidth(6, 100)  # last seen

        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(False)
        self.setShowGrid(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.setStyleSheet(f"""
            QTableWidget {{
                background: {BG_BASE};
                color: {TEXT_PRIMARY};
                border: none;
                font-size: 12px;
                outline: none;
            }}
            QTableWidget::item {{
                padding: 10px 12px;
                border-bottom: 1px solid {BORDER};
                background: transparent;
            }}
            QTableWidget::item:selected {{
                background: {BG_HOVER};
                color: {TEXT_PRIMARY};
                border-left: 2px solid {ACCENT};
            }}
            QHeaderView::section {{
                background: {BG_BASE};
                color: {TEXT_MUTED};
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 1.5px;
                text-transform: uppercase;
                padding: 0 12px;
                border: none;
                border-bottom: 1px solid {BORDER};
                height: 36px;
            }}
            QScrollBar:vertical {{
                background: {BG_SURFACE};
                width: 4px;
                border-radius: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER_BRIGHT};
                border-radius: 2px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

    def update_printer(self, p: dict):
        ip = p.get("ip", "")
        # Find existing row
        row = -1
        for i in range(self.rowCount()):
            if self.item(i, self.IP_COL) and self.item(i, self.IP_COL).text() == ip:
                row = i
                break
        if row == -1:
            row = self.rowCount()
            self.insertRow(row)
            self.setRowHeight(row, 52)

        is_online = p.get("is_online", False)
        color_online  = QColor(ACCENT)
        color_offline = QColor(ACCENT_DANGER)
        row_color     = color_online if is_online else color_offline

        # Col 0 — colored dot (via background trick)
        dot = QTableWidgetItem()
        dot.setBackground(QBrush(row_color))
        dot.setFlags(Qt.ItemFlag.NoItemFlags)
        self.setItem(row, 0, dot)

        # Col 1 — Status
        status_txt = p.get("status", "Unknown")
        status_item = QTableWidgetItem(f"  {status_txt}")
        status_item.setForeground(QBrush(row_color))
        self.setItem(row, 1, status_item)

        # Col 2 — IP
        self.setItem(row, 2, QTableWidgetItem(ip))

        # Col 3 — Hostname
        self.setItem(row, 3, QTableWidgetItem(p.get("hostname") or ""))

        # Col 4 — Brand / Model
        brand_model = f"{p.get('brand') or ''} {p.get('model') or ''}".strip() or "Unknown Device"
        bm_item = QTableWidgetItem(brand_model)
        bm_item.setFont(QFont(FONT_MAIN, 11))
        self.setItem(row, 4, bm_item)

        # Col 5 — Supplies (Toner Pills)
        consumables = p.get("consumables", [])
        if consumables:
            cell = QWidget()
            cell.setStyleSheet("background: transparent;")
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(10, 6, 10, 6)
            cl.setSpacing(4)
            for c in consumables[:4]:  # max 4 pills to keep row height sane
                pill = TonerPill(c.get("level", 0), c.get("max_capacity", 100), c.get("name", ""))
                cl.addWidget(pill)
            self.setCellWidget(row, 5, cell)
            row_h = max(52, len(consumables[:4]) * 26 + 20)
            self.setRowHeight(row, row_h)
        else:
            none_item = QTableWidgetItem("  No toner data")
            none_item.setForeground(QBrush(QColor(TEXT_MUTED)))
            self.setItem(row, 5, none_item)

        # Col 6 — Last Seen
        last_seen = p.get("last_seen", "")
        if last_seen and "T" in last_seen:
            last_seen = last_seen.split("T")[0]
        self.setItem(row, 6, QTableWidgetItem(last_seen))

    def copy_selection(self):
        rows = self.selectedRanges()
        if not rows:
            return
        lines = []
        for rng in rows:
            for r in range(rng.topRow(), rng.bottomRow() + 1):
                cells = []
                for c in [2, 3, 4, 6]:  # IP, Hostname, Model, LastSeen
                    it = self.item(r, c)
                    cells.append(it.text() if it else "")
                lines.append("\t".join(cells))
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText("\n".join(lines))


# ── Nav Button ────────────────────────────────────────────────────────────────

class NavButton(QPushButton):
    """Premium sidebar nav button."""

    def __init__(self, icon: str, label: str, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedHeight(54)
        self.setText(f"  {icon}  {label}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style(False)

    def _update_style(self, checked: bool):
        if checked:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {BG_CARD};
                    border: none;
                    border-left: 3px solid {ACCENT};
                    color: {ACCENT};
                    text-align: left;
                    padding-left: 20px;
                    font-size: 12px;
                    font-weight: 700;
                    letter-spacing: 0.5px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    border-left: 3px solid transparent;
                    color: {TEXT_SECONDARY};
                    text-align: left;
                    padding-left: 20px;
                    font-size: 12px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background: {BG_CARD};
                    color: {TEXT_PRIMARY};
                    border-left-color: {BORDER_BRIGHT};
                }}
            """)

    def setChecked(self, v: bool):
        super().setChecked(v)
        self._update_style(v)


# ── Side Nav Bar ──────────────────────────────────────────────────────────────

class SideNavBar(QFrame):
    """Premium collapsible side navigation."""

    nav_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("side_nav")
        self.setFixedWidth(220)
        self.setStyleSheet(f"""
            QFrame#side_nav {{
                background: {BG_SURFACE};
                border-right: 1px solid {BORDER};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Logo
        logo_frame = QFrame()
        logo_frame.setFixedHeight(72)
        logo_frame.setStyleSheet(f"border-bottom: 1px solid {BORDER}; background: {BG_SURFACE};")
        logo_layout = QVBoxLayout(logo_frame)
        logo_layout.setContentsMargins(22, 0, 0, 0)

        name_lbl = QLabel("PRINTSCOPE")
        name_lbl.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 15px; font-weight: 900; letter-spacing: 3px;"
        )
        tag_lbl = QLabel("Enterprise Fleet Monitor")
        tag_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9px; letter-spacing: 0.5px;")
        logo_layout.addWidget(name_lbl)
        logo_layout.addWidget(tag_lbl)
        layout.addWidget(logo_frame)

        # Spacer
        layout.addSpacing(12)

        # Nav buttons
        self._buttons: List[NavButton] = []
        self._add_btn("🌐", "Devices",     0)
        self._add_btn("📊", "Analytics",   1)
        self._add_btn("🛠", "Diagnostics", 2)
        self._add_btn("⚙", "Settings",    3)

        layout.addStretch()

        # Footer
        footer_lbl = QLabel("v3.1 Executive")
        footer_lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 9px; padding: 20px 22px; letter-spacing: 0.5px;"
        )
        layout.addWidget(footer_lbl)

    def _add_btn(self, icon: str, label: str, idx: int):
        btn = NavButton(icon, label)
        btn.clicked.connect(lambda _, i=idx: self._on_click(i))
        if idx == 0:
            btn.setChecked(True)
        self.layout().addWidget(btn)
        self._buttons.append(btn)

    def _on_click(self, idx: int):
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == idx)
        self.nav_changed.emit(idx)


# ── Fleet Health Gauge ────────────────────────────────────────────────────────

class FleetHealthGauge(QWidget):
    """Custom circular gauge showing fleet health score 0-100."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(160, 160)
        self._value = 0
        self._color = QColor(ACCENT)

    def set_value(self, v: int):
        self._value = max(0, min(100, v))
        if self._value < 40:
            self._color = QColor(ACCENT_DANGER)
        elif self._value < 70:
            self._color = QColor(ACCENT_WARN)
        else:
            self._color = QColor(ACCENT)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        r = min(w, h) // 2 - 12

        # Outer ring track
        pen = QPen(QColor(BORDER), 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # Progress arc
        if self._value > 0:
            arc_pen = QPen(self._color, 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            p.setPen(arc_pen)
            span = int(self._value / 100 * 360 * 16)
            p.drawArc(cx - r, cy - r, r * 2, r * 2, 90 * 16, -span)

        # Center value text
        p.setPen(QColor(TEXT_PRIMARY))
        f = QFont("Segoe UI", 26)
        f.setWeight(QFont.Weight.Black)
        p.setFont(f)
        p.drawText(0, 0, w, h - 16, Qt.AlignmentFlag.AlignCenter, f"{self._value}")

        # Label
        p.setPen(QColor(TEXT_MUTED))
        f2 = QFont("Segoe UI", 7)
        f2.setWeight(QFont.Weight.Bold)
        p.setFont(f2)
        p.drawText(0, h // 2 + 16, w, 20, Qt.AlignmentFlag.AlignCenter, "FLEET HEALTH")


# ── Device Supply Card ────────────────────────────────────────────────────────

class DeviceSupplyCard(QFrame):
    """Compact per-device card showing all supply levels."""

    def __init__(self, p_dict: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("device_card")
        self.setStyleSheet(f"""
            QFrame#device_card {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}
            QFrame#device_card:hover {{
                border-color: {BORDER_BRIGHT};
                background: {BG_HOVER};
            }}
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Header: status dot + model
        hdr = QHBoxLayout()
        hdr.setSpacing(6)
        is_online = p_dict.get("is_online", False)
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {ACCENT if is_online else ACCENT_DANGER}; font-size: 8px;")
        hdr.addWidget(dot)

        brand_model = f"{p_dict.get('brand') or ''} {p_dict.get('model') or p_dict['ip']}".strip()
        model_lbl = QLabel(brand_model[:32])
        model_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 11px; font-weight: 700;")
        hdr.addWidget(model_lbl)
        hdr.addStretch()

        ip_lbl = QLabel(p_dict["ip"])
        ip_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9px;")
        hdr.addWidget(ip_lbl)
        layout.addLayout(hdr)

        # Supply pills
        consumables = p_dict.get("consumables", [])
        if consumables:
            for c in consumables[:5]:
                row = QHBoxLayout()
                row.setSpacing(8)
                name_lbl = QLabel(c.get("name", "Supply")[:18])
                name_lbl.setFixedWidth(100)
                name_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 9px;")
                pill = TonerPill(c.get("level", 0), c.get("max_capacity", 100), c.get("name", ""))
                row.addWidget(name_lbl)
                row.addWidget(pill)
                layout.addLayout(row)
        else:
            no_data = QLabel("No toner data detected")
            no_data.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9px; font-style: italic;")
            layout.addWidget(no_data)


# ── Analytics Dashboard ───────────────────────────────────────────────────────

class AnalyticsDashboard(QWidget):
    """Fleet Intelligence Hub — KPIs, health gauge, risk alerts, supply grid."""

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.setStyleSheet(f"background: {BG_BASE};")

        # Outer scroll
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"background: {BG_BASE}; border: none;")
        scroll.verticalScrollBar().setStyleSheet(f"""
            QScrollBar:vertical {{ background: {BG_BASE}; width: 4px; border-radius: 2px; }}
            QScrollBar::handle:vertical {{ background: {BORDER_BRIGHT}; border-radius: 2px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        outer.addWidget(scroll)

        body = QWidget()
        body.setStyleSheet(f"background: {BG_BASE};")
        self._root = QVBoxLayout(body)
        self._root.setContentsMargins(40, 36, 40, 36)
        self._root.setSpacing(28)
        scroll.setWidget(body)

        # ── Header ──────────────────────────────────────────────────────────
        h_lbl = QLabel("Fleet Intelligence")
        h_lbl.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 26px; font-weight: 800; letter-spacing: -0.5px;"
        )
        sub_lbl = QLabel("Live health metrics · Predictive supply forecasting · Risk alerting")
        sub_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        self._root.addWidget(h_lbl)
        self._root.addWidget(sub_lbl)

        # ── Top Row: Gauge + KPIs ────────────────────────────────────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(20)

        # Gauge card
        gauge_frame = QFrame()
        gauge_frame.setObjectName("gauge_frame")
        gauge_frame.setStyleSheet(f"""
            QFrame#gauge_frame {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}
        """)
        gauge_frame.setFixedWidth(200)
        gauge_layout = QVBoxLayout(gauge_frame)
        gauge_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gauge = FleetHealthGauge()
        gauge_layout.addWidget(self.gauge, alignment=Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(gauge_frame)

        # KPIs stack
        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(14)
        self.kpi_total  = StatCard("Total Devices",  "📡", ACCENT_BLUE)
        self.kpi_online = StatCard("Online",         "●",  ACCENT)
        self.kpi_avg    = StatCard("Avg Toner",      "💧", ACCENT_PURPLE)
        self.kpi_risk   = StatCard("At Risk",        "⚠", ACCENT_DANGER)
        self.kpi_offline= StatCard("Offline",        "○",  ACCENT_DANGER)
        self.kpi_supply = StatCard("No Toner Data",  "?",  TEXT_SECONDARY)
        kpi_grid.addWidget(self.kpi_total,   0, 0)
        kpi_grid.addWidget(self.kpi_online,  0, 1)
        kpi_grid.addWidget(self.kpi_avg,     0, 2)
        kpi_grid.addWidget(self.kpi_risk,    1, 0)
        kpi_grid.addWidget(self.kpi_offline, 1, 1)
        kpi_grid.addWidget(self.kpi_supply,  1, 2)
        top_row.addLayout(kpi_grid, 1)
        self._root.addLayout(top_row)

        # ── Proactive Alerts Panel ────────────────────────────────────────────
        alerts_frame = QFrame()
        alerts_frame.setObjectName("alerts_frame")
        alerts_frame.setStyleSheet(f"""
            QFrame#alerts_frame {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}
        """)
        al = QVBoxLayout(alerts_frame)
        al.setContentsMargins(28, 22, 28, 22)
        al.setSpacing(10)

        al_hdr = QLabel("PROACTIVE ALERTS")
        al_hdr.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 9px; font-weight: 800; letter-spacing: 2px;"
        )
        al.addWidget(al_hdr)
        self._alerts_lbl = QLabel("Run a scan to populate fleet intelligence data.")
        self._alerts_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; line-height: 1.7;")
        self._alerts_lbl.setWordWrap(True)
        self._alerts_lbl.setTextFormat(Qt.TextFormat.RichText)
        al.addWidget(self._alerts_lbl)
        self._root.addWidget(alerts_frame)

        # ── Device Supply Grid ────────────────────────────────────────────────
        grid_hdr = QLabel("DEVICE SUPPLY STATUS")
        grid_hdr.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 9px; font-weight: 800; letter-spacing: 2px;"
        )
        self._root.addWidget(grid_hdr)

        self._grid_container = QWidget()
        self._grid_container.setStyleSheet(f"background: {BG_BASE};")
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setSpacing(14)
        self._root.addWidget(self._grid_container)
        self._root.addStretch()

    def refresh_data(self):
        printers = list(self.data_manager.printers.values())
        if not printers:
            return

        total   = len(printers)
        online  = sum(1 for p in printers if p.is_online)
        offline = total - online
        no_data = sum(1 for p in printers if not p.consumables)

        levels, risks = [], []
        for p in printers:
            if p.consumables:
                avg = sum(c.percentage for c in p.consumables) / len(p.consumables)
                levels.append(avg)
                if avg < 20:
                    days_txt = ""
                    for c in p.consumables:
                        d = p.estimate_days_remaining(c.name)
                        if d is not None:
                            days_txt = f" <span style='color:{ACCENT_DANGER}'>~{d}d left</span>"
                            break
                    label = f"{p.brand or ''} {p.model or p.ip}".strip()
                    risks.append(
                        f"<span style='color:{ACCENT_DANGER}'>⚠</span> "
                        f"<b style='color:{TEXT_PRIMARY}'>{label}</b> "
                        f"<span style='color:{TEXT_MUTED}'>{p.ip}</span> — "
                        f"<span style='color:{ACCENT_WARN}'>{int(avg)}% avg toner</span>{days_txt}"
                    )

        avg_lv = int(sum(levels) / len(levels)) if levels else 0
        pct_on = int(online / total * 100) if total else 0

        # Health score: weighted average of online % and toner avg
        health = int(pct_on * 0.5 + avg_lv * 0.5)
        self.gauge.set_value(health)

        self.kpi_total.set_value(total)
        self.kpi_online.set_value(f"{pct_on}%")
        self.kpi_avg.set_value(f"{avg_lv}%")
        self.kpi_risk.set_value(len(risks))
        self.kpi_offline.set_value(offline)
        self.kpi_supply.set_value(no_data)

        if risks:
            self._alerts_lbl.setText("<br>".join(risks))
        else:
            self._alerts_lbl.setText(
                f"<span style='color:{ACCENT}'>✓ All {total} devices within healthy parameters.</span>"
            )

        # Rebuild device grid
        # Remove old cards
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        cols = 3
        for i, p in enumerate(printers):
            card = DeviceSupplyCard(p.to_dict())
            self._grid_layout.addWidget(card, i // cols, i % cols)


# ── Diagnostics Console ───────────────────────────────────────────────────────

class DiagnosticsConsole(QTextEdit):
    """Monospace live-feed log console."""

    LEVEL_COLORS = {
        "DEBUG":   TEXT_MUTED,
        "INFO":    ACCENT_BLUE,
        "WARNING": ACCENT_WARN,
        "ERROR":   ACCENT_DANGER,
        "SUCCESS": ACCENT,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.setStyleSheet(f"""
            QTextEdit {{
                background: {BG_SURFACE};
                color: {TEXT_PRIMARY};
                font-family: {FONT_MONO};
                font-size: 11px;
                border: none;
                padding: 12px;
            }}
            QScrollBar:vertical {{
                background: {BG_SURFACE};
                width: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER_BRIGHT};
                border-radius: 2px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        self.log("SUCCESS", "PrintScope diagnostic engine initialized.")
        self.log("INFO", "Ready — waiting for discovery events.")

    def log(self, level: str, msg: str):
        ts    = datetime.datetime.now().strftime("%H:%M:%S")
        color = self.LEVEL_COLORS.get(level, TEXT_SECONDARY)
        entry = (
            f"<span style='color:{TEXT_MUTED}'>[{ts}]</span> "
            f"<span style='color:{color};font-weight:700'>[{level:<7}]</span> "
            f"<span style='color:{TEXT_PRIMARY}'>{msg}</span>"
        )
        self.append(entry)
        sb = self.verticalScrollBar()
        sb.setValue(sb.maximum())
