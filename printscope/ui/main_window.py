import sys
import asyncio
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLineEdit, QLabel, QTableWidget,
    QStatusBar, QToolBar, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QAction
from printscope.ui.components import PrinterTable
from printscope.discovery.scanner import NetworkScanner, generate_ip_range
from printscope.discovery.snmp_engine import SNMPEngine
from printscope.discovery.bonjour_engine import discover_mdns
from printscope.data.manager import PrinterManager

class DiscoveryWorker(QThread):
    """Worker thread for network discovery."""
    printer_found = pyqtSignal(dict)
    finished = pyqtSignal()
    progress = pyqtSignal(str)

    def __init__(self, start_ip, end_ip):
        super().__init__()
        self.start_ip = start_ip
        self.end_ip = end_ip

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        ips = generate_ip_range(self.start_ip, self.end_ip)
        self.progress.emit(f"Scanning {len(ips)} addresses...")
        
        scanner = NetworkScanner()
        snmp = SNMPEngine()
        
        # 1. mDNS Discovery (fast)
        self.progress.emit("Running mDNS discovery...")
        mdns_printers = loop.run_until_complete(discover_mdns(2.0))
        for p in mdns_printers:
            # Enrich with SNMP if possible
            enriched = snmp.get_printer_details(p.ip)
            self.printer_found.emit((enriched or p).to_dict())

        # 2. Port Scan Discovery
        self.progress.emit("Scanning for printer ports...")
        candidates = loop.run_until_complete(scanner.scan_range(ips))
        
        for ip in candidates:
            # Skip if already found via mDNS
            if any(p.ip == ip for p in mdns_printers):
                continue
                
            self.progress.emit(f"Querying {ip}...")
            p = snmp.get_printer_details(ip)
            if p:
                self.printer_found.emit(p.to_dict())
            else:
                # Basic info if SNMP fails but ports are open
                from printscope.models.printer import Printer
                p = Printer(ip=ip, status="Online", is_online=True, model="Network Device")
                self.printer_found.emit(p.to_dict())

        self.finished.emit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PrintScope - Network Printer Discovery")
        self.resize(1000, 600)
        
        self.data_manager = PrinterManager()
        
        self.setup_ui()
        self.load_initial_data()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Controls
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("IP Range:"))
        self.start_ip_input = QLineEdit("192.168.1.1")
        self.end_ip_input = QLineEdit("192.168.1.255")
        ctrl_layout.addWidget(self.start_ip_input)
        ctrl_layout.addWidget(QLabel("-"))
        ctrl_layout.addWidget(self.end_ip_input)
        
        self.scan_btn = QPushButton("Start Scan")
        self.scan_btn.clicked.connect(self.start_scan)
        ctrl_layout.addWidget(self.scan_btn)
        
        ctrl_layout.addStretch()

        self.auto_refresh_cb = QPushButton("Auto-Refresh: Off")
        self.auto_refresh_cb.setCheckable(True)
        self.auto_refresh_cb.clicked.connect(self.toggle_auto_refresh)
        ctrl_layout.addWidget(self.auto_refresh_cb)
        
        self.export_btn = QPushButton("Export")
        self.export_btn.clicked.connect(self.export_data)
        ctrl_layout.addWidget(self.export_btn)
        
        layout.addLayout(ctrl_layout)

        # Table
        self.table = PrinterTable()
        layout.addWidget(self.table)
        
        # Status Bar
        self.statusBar().showMessage("Ready")
        
        # Timer for auto-refresh
        from PyQt6.QtCore import QTimer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.start_scan)
        
        # Context menu for table
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, pos):
        from PyQt6.QtWidgets import QMenu
        menu = QMenu()
        open_web_action = menu.addAction("Open Web Interface")
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        
        if action == open_web_action:
            row = self.table.currentRow()
            if row != -1:
                ip = self.table.item(row, 1).text()
                import webbrowser
                webbrowser.open(f"http://{ip}")

    def toggle_auto_refresh(self):
        if self.auto_refresh_cb.isChecked():
            self.auto_refresh_cb.setText("Auto-Refresh: On")
            self.refresh_timer.start(60000) # 1 minute
        else:
            self.auto_refresh_cb.setText("Auto-Refresh: Off")
            self.refresh_timer.stop()
        for p in self.data_manager.printers.values():
            self.table.update_printer(p.to_dict())

    def start_scan(self):
        start_ip = self.start_ip_input.text()
        end_ip = self.end_ip_input.text()
        
        self.scan_btn.setEnabled(False)
        self.statusBar().showMessage("Scanning...")
        
        self.worker = DiscoveryWorker(start_ip, end_ip)
        self.worker.printer_found.connect(self.handle_printer_found)
        self.worker.progress.connect(lambda msg: self.statusBar().showMessage(msg))
        self.worker.finished.connect(self.scan_finished)
        self.worker.start()

    def handle_printer_found(self, p_dict):
        from printscope.models.printer import Printer, Consumable
        from datetime import datetime
        
        # Create Printer object from dict for manager
        p = Printer(
            ip=p_dict["ip"],
            hostname=p_dict["hostname"],
            brand=p_dict["brand"],
            model=p_dict["model"],
            serial_number=p_dict["serial_number"],
            status=p_dict["status"],
            is_online=p_dict["is_online"],
            last_seen=datetime.fromisoformat(p_dict["last_seen"]),
            web_interface_url=p_dict["web_interface_url"]
        )
        p.consumables = [Consumable(c["name"], c["level"], c["max_capacity"]) for c in p_dict["consumables"]]
        
        self.data_manager.add_or_update_printer(p)
        self.table.update_printer(p.to_dict())

    def scan_finished(self):
        self.scan_btn.setEnabled(True)
        self.statusBar().showMessage("Scan complete")

    def export_data(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Data", "", "CSV Files (*.csv);;JSON Files (*.json)")
        if path:
            if path.endswith(".csv"):
                self.data_manager.export_csv(path)
            else:
                self.data_manager.export_json(path)
            QMessageBox.information(self, "Export", f"Data exported to {path}")
