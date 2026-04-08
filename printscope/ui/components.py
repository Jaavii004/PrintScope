from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, 
    QWidget, QHBoxLayout, QLabel, QVBoxLayout
)
from PyQt6.QtCore import Qt

class TonerProgressBar(QProgressBar):
    """Premium progress bar for toner levels with a modern, glowing look."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFormat("%p%")
        self.setFixedHeight(18) # Slightly taller for better visibility

    def set_level(self, level, max_cap):
        self.setMaximum(max_cap if max_cap > 0 else 100)
        self.setValue(level if level >= 0 else 0)
        
        # Color logic (Vibrant Gradients)
        percentage = (level / max_cap * 100) if max_cap > 0 else 0
        if percentage < 15:
            color = "#e74c3c" # Soft Coral Red
        elif percentage < 40:
            color = "#f39c12" # Flat Orange
        else:
            color = "#27ae60" # Soft Forest Green
            
        self.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid #333;
                background-color: #252526;
                text-align: center;
                color: #ffffff;
                font-size: 10px;
                font-weight: 500;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 1px;
            }}
        """)
        
        # Predictive tooltip
        est_days = getattr(self, "est_days", None)
        if est_days is not None:
            self.setToolTip(f"{self.format()}: {est_days} days remaining (est.)")
        else:
            self.setToolTip(f"{self.format()} (Gathering data...)")

class StatCard(QWidget):
    """A sleek card for the dashboard showing a single statistic."""
    def __init__(self, title, icon_text, color="#3498db", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)
        
        self.title_label = QLabel(title.upper())
        self.title_label.setStyleSheet("color: #aeaeae; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;")
        
        self.value_label = QLabel("0")
        self.value_label.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: bold;")
        
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        
        self.setStyleSheet(f"""
            StatCard {{
                background-color: #252526;
                border: 1px solid #3e3e42;
                border-radius: 4px;
            }}
            StatCard:hover {{
                border-color: {color};
                background-color: #2d2d30;
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
        self.setFixedHeight(120)
        self.history = [] # List of (timestamp, level)
        self.color = QColor("#3498db")
        self.setObjectName("trend_chart")
        self.setToolTip("Consumable Usage Trend (Last 50 Scans)")

    def set_data(self, history, color="#3498db"):
        self.history = history
        self.color = QColor(color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Outer Border & Background
        painter.setPen(QPen(QColor("#3e3e42"), 1))
        painter.setBrush(QColor("#1e1e1e"))
        painter.drawRoundedRect(self.rect().adjusted(1,1,-1,-1), 4, 4)
        
        if not self.history or len(self.history) < 2:
            return
            
        w, h = self.width(), self.height()
        padding = 15
        
        # Draw Background Grid (Subtle)
        grid_pen = QPen(QColor("#2d2d2d"), 1)
        painter.setPen(grid_pen)
        for i in range(1, 4):
            y = int(padding + (h - 2*padding) * i / 4)
            painter.drawLine(padding + 5, y, w - padding - 5, y)
            
        # Draw Axis (Subtle)
        painter.setPen(QPen(QColor("#3e3e42"), 1))
        painter.drawLine(padding, h - padding, w - padding, h - padding)
        
        # Prepare Points
        points = []
        max_val = 100
        min_val = 0
        
        # Limit to last 50 points if more exist
        data = self.history[-50:]
        
        for i, (ts, val) in enumerate(data):
            x = padding + (w - 2*padding) * i / (len(data) - 1)
            y = h - padding - (h - 2*padding) * (val / max_val)
            points.append(QPointF(x, y))
            
        # Draw Line (Premium Glow/Solid)
        pen = QPen(self.color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        
        path = QPolygonF(points)
        painter.drawPolyline(path)
        
        # Fill Area (Gradient)
        fill_color = QColor(self.color)
        fill_color.setAlpha(40)
        painter.setBrush(fill_color)
        painter.setPen(Qt.PenStyle.NoPen)
        
        area_points = [QPointF(padding, h - padding)] + points + [QPointF(points[-1].x(), h - padding)]
        painter.drawPolygon(QPolygonF(area_points))

class DetailsSidebar(QWidget):
    """A side panel for displaying detailed printer information."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(280)
        self.setObjectName("sidebar")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 20, 15, 15)
        layout.setSpacing(15)
        
        # Header
        self.header = QLabel("DETAILS")
        self.header.setStyleSheet("font-weight: bold; color: #3498db; font-size: 12px; letter-spacing: 1px;")
        layout.addWidget(self.header)
        
        # Info Area (Scrollable)
        from PyQt6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        
        scroll_content = QWidget()
        self.info_layout = QVBoxLayout(scroll_content)
        self.info_layout.setContentsMargins(0, 0, 0, 0)
        self.info_layout.setSpacing(6)
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # Trend Chart
        self.chart_label = QLabel("USAGE TREND")
        self.chart_label.setStyleSheet("color: #888888; font-size: 9px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(self.chart_label)
        
        self.trend_chart = UsageTrendChart()
        layout.addWidget(self.trend_chart)
        
        self.setStyleSheet("""
            #sidebar {
                background-color: #252526;
                border-left: 1px solid #3e3e42;
            }
        """)
        
        self.hide() # Hidden by default

    def clear_info(self):
        while self.info_layout.count():
            item = self.info_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def add_field(self, label, value):
        l = QLabel(label.upper())
        l.setStyleSheet("color: #888888; font-size: 9px; font-weight: bold;")
        v = QLabel(str(value) if value else "—")
        v.setStyleSheet("color: #e1e1e1; font-size: 11px; margin-bottom: 4px;")
        v.setWordWrap(True)
        self.info_layout.addWidget(l)
        self.info_layout.addWidget(v)

    def update_details(self, p_dict):
        self.clear_info()
        self.show()
        
        self.add_field("Brand", p_dict.get("brand"))
        self.add_field("Model", p_dict.get("model"))
        self.add_field("Current Status", p_dict.get("status"))
        self.add_field("IPv4 Address", p_dict.get("ip"))
        self.add_field("DNS Hostname", p_dict.get("hostname"))
        self.add_field("Hardware MAC", p_dict.get("mac_address"))
        self.add_field("Serial", p_dict.get("serial_number"))
        self.add_field("Assigned Location", p_dict.get("location"))
        self.add_field("SysUptime", p_dict.get("uptime"))
        self.add_field("Detected On", p_dict.get("last_seen", "").split('T')[0])
        
        # Process History for Chart
        if p_dict.get("history"):
            # Extract levels for the first primary consumable (usually Black toner)
            # Simplified: we look for the first consumable in the history
            chart_data = []
            for entry in p_dict["history"]:
                if entry.get("consumables"):
                    lvl = entry["consumables"][0]["level"]
                    ts = entry["timestamp"]
                    chart_data.append((ts, lvl))
            
            if chart_data:
                self.chart_label.show()
                self.trend_chart.show()
                self.trend_chart.set_data(chart_data)
            else:
                self.chart_label.hide()
                self.trend_chart.hide()
        else:
            self.chart_label.hide()
            self.trend_chart.hide()

class PrinterTable(QTableWidget):
    """Table to display discovered printers with a standard networking tool look."""
    
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.setColumnCount(7)
        self.setHorizontalHeaderLabels([
            "Status", "IP Address", "Hostname", "Manufacturer", "Model", "Supplies", "Last Seen"
        ])
        
        # Premium Dark Look
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setShowGrid(False) # Clean, borderless look
        self.verticalHeader().setVisible(False)
        
        self.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e1e;
                alternate-background-color: #252526;
                color: #cccccc;
                border: none;
                font-size: 12px;
                selection-background-color: #094771;
                selection-color: #ffffff;
            }
            QHeaderView::section {
                background-color: #252526;
                color: #888888;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #333;
                font-weight: bold;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                font-size: 10px;
            }
            QTableWidget::item {
                padding: 6px 8px;
                border: none;
            }
            QTableWidget::item:selected {
                border-left: 3px solid #3498db;
            }
        """)

    def update_printer(self, printer_dict):
        """Update or add a printer to the table."""
        try:
            import logging
            logger = logging.getLogger("PrintScope")
            logger.info(f"Updating table for printer: {printer_dict.get('ip')}")
            
            row = -1
            for i in range(self.rowCount()):
                item = self.item(i, 1)
                if item and item.text() == printer_dict["ip"]:
                    row = i
                    break
            
            if row == -1:
                row = self.rowCount()
                self.insertRow(row)
                self.setItem(row, 1, QTableWidgetItem(printer_dict["ip"]))
                
            # Status Indicator
            status = printer_dict["status"]
            status_item = QTableWidgetItem(f" ● {status}")
            if printer_dict["is_online"]:
                status_item.setForeground(Qt.GlobalColor.green)
            else:
                status_item.setForeground(Qt.GlobalColor.red)
            self.setItem(row, 0, status_item)
            
            # Info
            self.setItem(row, 2, QTableWidgetItem(printer_dict["hostname"]))
            self.setItem(row, 3, QTableWidgetItem(printer_dict["brand"]))
            self.setItem(row, 4, QTableWidgetItem(printer_dict["model"]))
            self.setItem(row, 6, QTableWidgetItem(printer_dict.get("last_seen", "")))
            
            # Supplies (Consumables)
            if printer_dict.get("consumables"):
                container = QWidget()
                layout = QVBoxLayout(container)
                layout.setContentsMargins(1, 1, 1, 1)
                layout.setSpacing(1)
                
                for c in printer_dict["consumables"]:
                    bar = TonerProgressBar()
                    bar.est_days = c.get("est_days")
                    bar.set_level(c["level"], c["max_capacity"])
                    layout.addWidget(bar)
                
                self.setCellWidget(row, 5, container)
                # Ensure row is tall enough for all bars
                self.setRowHeight(row, max(40, len(printer_dict["consumables"]) * 20 + 10))
            else:
                self.setItem(row, 5, QTableWidgetItem("N/A"))
        except Exception as e:
            import traceback
            import logging
            logging.getLogger("PrintScope").error(f"Error updating table: {e}")
            traceback.print_exc()

    def copy_selection(self):
        """Copy selected rows to clipboard."""
        selected_ranges = self.selectedRanges()
        if not selected_ranges:
            return
            
        lines = []
        for r in selected_ranges:
            for row in range(r.topRow(), r.bottomRow() + 1):
                row_data = []
                for col in range(self.columnCount()):
                    if col == 5:
                        row_data.append("Check App for Levels")
                    else:
                        item = self.item(row, col)
                        row_data.append(item.text() if item else "")
                lines.append("\t".join(row_data))
        
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText("\n".join(lines))
