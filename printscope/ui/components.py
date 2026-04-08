from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, 
    QWidget, QHBoxLayout, QLabel, QVBoxLayout
)
from PyQt6.QtCore import Qt

class TonerPill(QWidget):
    """A minimal, flat pill-style indicator for toner levels."""
    def __init__(self, level, max_cap, parent=None):
        super().__init__(parent)
        self.setFixedHeight(12)
        self.setMinimumWidth(80)
        self.level = level
        self.max_cap = max_cap
        
        # Color logic
        pct = (level / max_cap * 100) if max_cap > 0 else 0
        if pct < 15: self.color = QColor("#e74c3c")
        elif pct < 40: self.color = QColor("#f39c12")
        else: self.color = QColor("#27ae60")
        
        self.setToolTip(f"{int(pct)}% Remaining")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#2d2d30"))
        painter.drawRoundedRect(self.rect(), 6, 6)
        
        # Fill pill
        if self.max_cap > 0:
            fill_w = int(self.width() * (self.level / self.max_cap))
            if fill_w > 0:
                painter.setBrush(self.color)
                painter.drawRoundedRect(0, 0, fill_w, self.height(), 6, 6)

class StatCard(QWidget):
    """A sleek card for the dashboard showing a single statistic."""
    def __init__(self, title, icon_text, color="#3498db", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self) # Horizontal for more compact look
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(12)
        
        self.icon_label = QLabel(icon_text)
        self.icon_label.setStyleSheet(f"font-size: 20px; color: {color};")
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(0)
        
        self.title_label = QLabel(title.upper())
        self.title_label.setStyleSheet("color: #888888; font-size: 9px; font-weight: bold; letter-spacing: 0.5px;")
        
        self.value_label = QLabel("0")
        self.value_label.setStyleSheet(f"color: #ffffff; font-size: 20px; font-weight: bold;")
        
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.value_label)
        
        layout.addWidget(self.icon_label)
        layout.addLayout(text_layout)
        layout.addStretch()
        
        self.setStyleSheet(f"""
            StatCard {{
                background-color: #252526;
                border: 1px solid #3e3e42;
                border-radius: 6px;
            }}
            StatCard:hover {{
                background-color: #2d2d30;
                border-color: {color};
            }}
        """)

    def set_value(self, value):
        self.value_label.setText(str(value))

from PyQt6.QtGui import QPainter, QPen, QColor, QPolygonF
from PyQt6.QtCore import QPointF

class UsageTrendChart(QWidget):
    """A bespoke custom-painted line chart for showing consumable level trends."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(130)
        self.history = [] # List of (timestamp, level)
        self.color = QColor("#007acc")
        self.setObjectName("trend_chart")

    def set_data(self, history, color="#007acc"):
        self.history = history
        self.color = QColor(color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background
        painter.setPen(QPen(QColor("#3e3e42"), 1))
        painter.setBrush(QColor("#1a1a1c"))
        painter.drawRoundedRect(self.rect().adjusted(1,1,-1,-1), 6, 6)
        
        if not self.history or len(self.history) < 2:
            return
            
        w, h = self.width(), self.height()
        padding = 20
        
        # Grid
        grid_pen = QPen(QColor("#2d2d2d"), 1)
        painter.setPen(grid_pen)
        for i in range(1, 4):
            y = int(padding + (h - 2*padding) * i / 4)
            painter.drawLine(padding, y, w - padding, y)
            
        # Draw Data
        data = self.history[-30:] # Last 30 points
        points = []
        for i, (ts, val) in enumerate(data):
            x = padding + (w - 2*padding) * i / (len(data) - 1)
            y = h - padding - (h - 2*padding) * (val / 100)
            points.append(QPointF(x, y))
            
        # Line Area Fill
        fill_color = QColor(self.color)
        fill_color.setAlpha(30)
        painter.setBrush(fill_color)
        painter.setPen(Qt.PenStyle.NoPen)
        area_pts = [QPointF(padding, h - padding)] + points + [QPointF(points[-1].x(), h - padding)]
        painter.drawPolygon(QPolygonF(area_pts))

        # Main Line
        line_pen = QPen(self.color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(line_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolyline(QPolygonF(points))
        
        # Markers
        painter.setPen(QPen(QColor("#ffffff"), 1))
        painter.setBrush(self.color)
        for pt in points:
            painter.drawEllipse(pt, 3, 3)

class DetailsSidebar(QWidget):
    """A side panel for displaying detailed printer information."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(280)
        self.setObjectName("sidebar")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 20, 15, 15)
        layout.setSpacing(12)
        
        # Header
        self.header = QLabel("DEVICE DETAILS")
        self.header.setStyleSheet("font-weight: bold; color: #007acc; font-size: 11px; letter-spacing: 1.5px;")
        layout.addWidget(self.header)
        
        from PyQt6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        
        scroll_content = QWidget()
        self.info_layout = QVBoxLayout(scroll_content)
        self.info_layout.setContentsMargins(0, 10, 0, 10)
        self.info_layout.setSpacing(12)
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # Trend Chart
        self.chart_label = QLabel("CONSUMABLE TREND")
        self.chart_label.setStyleSheet("color: #666666; font-size: 9px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(self.chart_label)
        
        self.trend_chart = UsageTrendChart()
        layout.addWidget(self.trend_chart)
        
        self.setStyleSheet("""
            #sidebar {
                background-color: #1e1e1e;
                border-left: 1px solid #2d2d2d;
            }
        """)
        self.hide()

    def clear_info(self):
        while self.info_layout.count():
            item = self.info_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def add_field(self, label, value):
        l = QLabel(label.upper())
        l.setStyleSheet("color: #666; font-size: 9px; font-weight: bold; letter-spacing: 0.5px;")
        v = QLabel(str(value) if value else "—")
        v.setStyleSheet("color: #cccccc; font-size: 11px; font-weight: 400;")
        v.setWordWrap(True)
        self.info_layout.addWidget(l)
        self.info_layout.addWidget(v)

    def update_details(self, p_dict):
        self.clear_info()
        self.show()
        self.add_field("Brand", p_dict.get("brand"))
        self.add_field("Model", p_dict.get("model"))
        self.add_field("Status", p_dict.get("status"))
        self.add_field("IP Address", p_dict.get("ip"))
        self.add_field("Hostname", p_dict.get("hostname"))
        self.add_field("MAC Address", p_dict.get("mac_address"))
        self.add_field("Serial", p_dict.get("serial_number"))
        self.add_field("Assigned Location", p_dict.get("location"))
        self.add_field("SysUptime", p_dict.get("uptime"))
        
        if p_dict.get("history"):
            chart_data = []
            for entry in p_dict["history"]:
                if entry.get("consumables"):
                    chart_data.append((entry["timestamp"], entry["consumables"][0]["level"]))
            if chart_data:
                self.chart_label.show(); self.trend_chart.show()
                self.trend_chart.set_data(chart_data)
            else:
                self.chart_label.hide(); self.trend_chart.hide()
        else:
            self.chart_label.hide(); self.trend_chart.hide()

class PrinterTable(QTableWidget):
    """Table to display discovered printers with an ultra-clean, gridless look."""
    def __init__(self, data_manager):
        super().__init__()
        self.setColumnCount(7)
        self.setHorizontalHeaderLabels(["Status", "IP Address", "Hostname", "Manufacturer", "Model", "Supplies", "Last Seen"])
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        self.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e1e;
                alternate-background-color: #232325;
                color: #cccccc;
                border: none;
                gridline-color: transparent;
                font-size: 12px;
                selection-background-color: transparent;
            }
            QHeaderView::section {
                background-color: #1e1e1e;
                color: #666666;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #2d2d2d;
                font-weight: bold;
                text-transform: uppercase;
                font-size: 10px;
                letter-spacing: 1px;
            }
            QTableWidget::item {
                padding: 10px;
                border-bottom: 1px solid #28282a;
            }
            QTableWidget::item:selected {
                background-color: #2d2d30;
                color: #ffffff;
                border-left: 3px solid #007acc;
            }
        """)

    def update_printer(self, p_dict):
        row = -1
        for i in range(self.rowCount()):
            item = self.item(i, 1)
            if item and item.text() == p_dict["ip"]:
                row = i; break
        if row == -1:
            row = self.rowCount(); self.insertRow(row)
            self.setItem(row, 1, QTableWidgetItem(p_dict["ip"]))
        
        status_item = QTableWidgetItem(f" ● {p_dict['status']}")
        status_item.setForeground(QColor("#27ae60") if p_dict["is_online"] else QColor("#e74c3c"))
        self.setItem(row, 0, status_item)
        self.setItem(row, 2, QTableWidgetItem(p_dict["hostname"]))
        self.setItem(row, 3, QTableWidgetItem(p_dict["brand"]))
        self.setItem(row, 4, QTableWidgetItem(p_dict["model"]))
        self.setItem(row, 6, QTableWidgetItem(p_dict.get("last_seen", "").split('T')[0]))
        
        if p_dict.get("consumables"):
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(10, 5, 10, 5); layout.setSpacing(4)
            for c in p_dict["consumables"]:
                layout.addWidget(TonerPill(c["level"], c["max_capacity"]))
            self.setCellWidget(row, 5, container)
            self.setRowHeight(row, max(45, len(p_dict["consumables"]) * 16 + 15))
        else:
            self.setItem(row, 5, QTableWidgetItem("—"))

    def copy_selection(self):
        ranges = self.selectedRanges()
        if not ranges: return
        rows = []
        for r in ranges:
            for row in range(r.topRow(), r.bottomRow() + 1):
                rows.append("\t".join([self.item(row, c).text() if self.item(row, c) else "" for c in [0,1,2,3,4,6]]))
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText("\n".join(rows))
