from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, 
    QWidget, QHBoxLayout, QLabel, QVBoxLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush

class StatusIndicator(QWidget):
    """Small colored circle to indicate online/offline status."""
    def __init__(self, status: str):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        self.label = QLabel()
        self.label.setFixedSize(12, 12)
        self.set_status(status)
        layout.addWidget(self.label)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_status(self, status: str):
        color = "grey"
        if status.lower() == "idle": color = "green"
        elif status.lower() == "printing": color = "blue"
        elif "error" in status.lower() or "offline" in status.lower(): color = "red"
        elif "warning" in status.lower() or "low" in status.lower(): color = "yellow"
        
        self.label.setStyleSheet(f"background-color: {color}; border-radius: 6px;")

class ConsumableProgressBar(QProgressBar):
    """Progress bar for ink/toner levels."""
    def __init__(self, percentage: int, name: str):
        super().__init__()
        self.setRange(0, 100)
        self.setValue(percentage)
        self.setTextVisible(True)
        self.setFormat(f"{name}: %v%")
        
        # Color based on level
        if percentage < 10:
            self.setStyleSheet("QProgressBar::chunk { background-color: red; }")
        elif percentage < 25:
            self.setStyleSheet("QProgressBar::chunk { background-color: orange; }")
        else:
            self.setStyleSheet("QProgressBar::chunk { background-color: #4CAF50; }")

class PrinterTable(QTableWidget):
    """Table to display discovered printers."""
    def __init__(self):
        super().__init__()
        headers = ["Status", "IP Address", "Hostname", "Brand", "Model", "Ink/Toner", "Last Seen"]
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(0, 60)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setStyleSheet("""
            QTableWidget {
                gridline-color: #d3d3d3;
                background-color: white;
                alternate-background-color: #f9f9f9;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 4px;
                border: 1px solid #d3d3d3;
                font-weight: bold;
            }
        """)

    def update_printer(self, printer_dict: dict):
        """Update or add a printer to the table."""
        # Find row by IP
        row = -1
        for i in range(self.rowCount()):
            if self.item(i, 1).text() == printer_dict["ip"]:
                row = i
                break
        
        if row == -1:
            row = self.rowCount()
            self.insertRow(row)
            self.setItem(row, 1, QTableWidgetItem(printer_dict["ip"]))

        # Status
        status_widget = StatusIndicator(printer_dict["status"])
        self.setCellWidget(row, 0, status_widget)

        # Details
        self.setItem(row, 2, QTableWidgetItem(printer_dict["hostname"] or "N/A"))
        self.setItem(row, 3, QTableWidgetItem(printer_dict["brand"] or "Generic"))
        self.setItem(row, 4, QTableWidgetItem(printer_dict["model"] or "N/A"))
        
        # Ink levels
        ink_layout = QVBoxLayout()
        ink_container = QWidget()
        ink_container.setLayout(ink_layout)
        ink_layout.setContentsMargins(2, 2, 2, 2)
        ink_layout.setSpacing(1)
        
        for c in printer_dict["consumables"][:2]: # Show only first 2 to keep row height sane
            bar = ConsumableProgressBar(c["percentage"], c["name"])
            bar.setFixedHeight(12)
            ink_layout.addWidget(bar)
        
        if not printer_dict["consumables"]:
            ink_layout.addWidget(QLabel("No data"))
            
        self.setCellWidget(row, 5, ink_container)
        self.setItem(row, 6, QTableWidgetItem(printer_dict["last_seen"]))
        self.item(row, 1).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
