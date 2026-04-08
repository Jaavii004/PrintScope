import sys
import asyncio
import socket
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLineEdit, QLabel, QTableWidget,
    QStatusBar, QToolBar, QFileDialog, QMessageBox,
    QSystemTrayIcon, QMenu, QProgressBar, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QIcon, QAction

from printscope.ui.components import PrinterTable, StatCard, DetailsSidebar
from printscope.discovery.scanner import NetworkScanner, generate_ip_range
from printscope.discovery.snmp_engine import SNMPEngine
from printscope.discovery.bonjour_engine import discover_mdns
from printscope.data.manager import PrinterManager

class DiscoveryWorker(QThread):
    """Worker thread for network discovery."""
    printer_found = pyqtSignal(dict)
    finished = pyqtSignal()
    progress = pyqtSignal(str)
    progress_val = pyqtSignal(int)
    current_ip = pyqtSignal(str)

    def __init__(self, start_ip, end_ip):
        super().__init__()
        self.start_ip = start_ip
        self.end_ip = end_ip

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._do_scan_async())
        except Exception as e:
            import traceback
            print(f"DiscoveryWorker crash: {e}")
            traceback.print_exc()
            self.progress.emit(f"Error during scan: {e}")
        finally:
            self.finished.emit()

    async def _do_scan_async(self):
        ips = generate_ip_range(self.start_ip, self.end_ip)
        total_ips = len(ips)
        self.progress.emit(f"Scanning {total_ips} addresses...")
        
        scanner = NetworkScanner(timeout=1.5, max_concurrency=60) # Increased concurrency
        snmp = SNMPEngine()
        
        # 1. mDNS Discovery (fast)
        self.current_ip.emit("mDNS/Bonjour")
        self.progress.emit("mDNS scanning...")
        try:
            mdns_printers = await discover_mdns(2.0)
            for p in mdns_printers:
                enriched = await snmp.get_printer_details_async(p.ip)
                self.printer_found.emit((enriched or p).to_dict())
        except Exception:
            mdns_printers = []

        # 2. Port Scan Discovery
        self.progress.emit("Port scanning...")
        try:
            candidates = await scanner.scan_range(ips)
        except Exception:
            candidates = []
        
        processed = 0
        for ip in candidates:
            processed += 1
            progress_pct = int((processed / len(candidates)) * 100) if candidates else 0
            self.progress_val.emit(progress_pct)
            
            if any(p.ip == ip for p in mdns_printers):
                continue
                
            self.current_ip.emit(ip)
            self.progress.emit(f"Checking {ip}...")
            try:
                p = await snmp.get_printer_details_async(ip)
                if p:
                    self.printer_found.emit(p.to_dict())
                else:
                    # Basic info if SNMP fails but ports are open
                    from printscope.models.printer import Printer
                    import logging
                    logger = logging.getLogger("PrintScope")
                    logger.info(f"SNMP failed for {ip}, showing as basic device")
                    p = Printer(ip=ip, status="Online", is_online=True, model="Network Device")
                    self.printer_found.emit(p.to_dict())
            except Exception as e:
                import logging
                logging.getLogger("PrintScope").error(f"Error checking {ip}: {e}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PrintScope - Network Scanner")
        self.resize(1100, 650)
        
        self.data_manager = PrinterManager()
        
        self.setup_ui()
        self.setup_tray()
        self.autodetect_ip_range()
        self.load_initial_data()

    def load_initial_data(self):
        for p in self.data_manager.printers.values():
            self.table.update_printer(p.to_dict())

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Dashboard Area
        self.dashboard = QFrame()
        self.dashboard.setObjectName("dashboard")
        dash_layout = QHBoxLayout(self.dashboard)
        dash_layout.setContentsMargins(30, 25, 30, 25) # More spacious
        dash_layout.setSpacing(20)
        
        self.stat_total = StatCard("Total Devices", "🖨️", "#007acc")
        self.stat_online = StatCard("Online Now", "🌐", "#27ae60")
        self.stat_alerts = StatCard("Low Supplies", "⚠️", "#e67e22")
        
        dash_layout.addWidget(self.stat_total)
        dash_layout.addWidget(self.stat_online)
        dash_layout.addWidget(self.stat_alerts)
        dash_layout.addStretch()
        
        main_layout.addWidget(self.dashboard)

        # 2. Control & Search Bar
        self.ctrl_bar = QFrame()
        self.ctrl_bar.setObjectName("ctrl_bar")
        ctrl_layout = QHBoxLayout(self.ctrl_bar)
        ctrl_layout.setContentsMargins(20, 10, 20, 10)
        ctrl_layout.setSpacing(15)
        
        # IP Range
        range_box = QHBoxLayout()
        range_box.addWidget(QLabel("RANGE:"))
        self.start_ip_input = QLineEdit("192.168.1.1")
        self.end_ip_input = QLineEdit("192.168.1.255")
        self.start_ip_input.setFixedWidth(110)
        self.end_ip_input.setFixedWidth(110)
        range_box.addWidget(self.start_ip_input)
        range_box.addWidget(QLabel("→"))
        range_box.addWidget(self.end_ip_input)
        ctrl_layout.addLayout(range_box)
        
        self.scan_btn = QPushButton("START NEW SCAN")
        self.scan_btn.setObjectName("scan_btn")
        self.scan_btn.setFixedWidth(150)
        self.scan_btn.clicked.connect(self.start_scan)
        ctrl_layout.addWidget(self.scan_btn)
        
        self.report_btn = QPushButton("GENERATE REPORT")
        self.report_btn.setObjectName("report_btn")
        self.report_btn.setFixedWidth(150)
        self.report_btn.clicked.connect(self.export_report)
        ctrl_layout.addWidget(self.report_btn)
        
        ctrl_layout.addSpacing(20)
        
        # Search Filter
        search_box = QHBoxLayout()
        search_box.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search printers (IP, Model, Brand)...")
        self.search_input.textChanged.connect(self.filter_table)
        search_box.addWidget(QLabel("🔍"))
        search_box.addWidget(self.search_input)
        ctrl_layout.addLayout(search_box)
        
        ctrl_layout.addStretch()
        
        self.auto_refresh_cb = QPushButton("Auto Scan: Off")
        self.auto_refresh_cb.setCheckable(True)
        self.auto_refresh_cb.setFixedWidth(120)
        self.auto_refresh_cb.clicked.connect(self.toggle_auto_refresh)
        ctrl_layout.addWidget(self.auto_refresh_cb)
        
        main_layout.addWidget(self.ctrl_bar)

        # 3. Progress Overlay (Horizontal)
        self.progress_container = QFrame()
        self.progress_container.setObjectName("progress_container")
        self.progress_container.setFixedHeight(30)
        prog_layout = QHBoxLayout(self.progress_container)
        prog_layout.setContentsMargins(20, 0, 20, 0)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { background-color: #1e1e1e; border-radius: 3px; border: none; }
            QProgressBar::chunk { background-color: #3498db; border-radius: 3px; }
        """)
        
        self.current_proc_label = QLabel("Waiting...")
        self.current_proc_label.setStyleSheet("font-size: 10px; color: #666;")
        
        prog_layout.addWidget(self.progress_bar)
        prog_layout.addWidget(self.current_proc_label)
        
        main_layout.addWidget(self.progress_container)
        self.progress_container.hide()

        # 4. Content Area (Table + Sidebar)
        content_box = QHBoxLayout()
        content_box.setContentsMargins(0, 0, 0, 0)
        content_box.setSpacing(0)
        
        self.table = PrinterTable(self.data_manager)
        self.table.itemSelectionChanged.connect(self.handle_selection_changed)
        content_box.addWidget(self.table)
        
        self.sidebar = DetailsSidebar()
        content_box.addWidget(self.sidebar)
        
        main_layout.addLayout(content_box)
        
        # Style
        self.apply_standard_styling()
        
        # Timers
        from PyQt6.QtCore import QTimer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.start_scan)
        
        self.alert_timer = QTimer()
        self.alert_timer.timeout.connect(self.check_alerts)
        self.alert_timer.start(60000)
        
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

    def export_report(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Inventory Report", "", "HTML Files (*.html)")
        if path:
            self.data_manager.export_html(path)
            QMessageBox.information(self, "Report Generated", f"Executive report saved to:\n{path}")

    def setup_tray(self):
        """Setup system tray icon and menu."""
        self.tray_icon = QSystemTrayIcon(self)
        # Using a standard icon if none exists
        self.tray_icon.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
        
        tray_menu = QMenu()
        restore_action = tray_menu.addAction("Restore PrintScope")
        restore_action.triggered.connect(self.showNormal)
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction("Exit App")
        quit_action.triggered.connect(sys.exit)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        self.tray_icon.activated.connect(self.tray_icon_activated)

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.showNormal()

    def check_alerts(self):
        """Check for low toner or printers going offline and notify user."""
        if not hasattr(self, "_notified_alerts"):
            self._notified_alerts = set()
            
        for p in self.data_manager.printers.values():
            if p.is_online:
                for c in p.consumables:
                    alert_key = f"{p.ip}_{c.name}_{c.level//10}" # Notify every 10% drop
                    if c.percentage < 10 and alert_key not in self._notified_alerts:
                        self.tray_icon.showMessage(
                            "Low Supplies Warning",
                            f"{p.brand} {p.model} ({p.ip}) is low on {c.name} ({c.percentage}%)",
                            QSystemTrayIcon.MessageIcon.Warning,
                            5000
                        )
                        self._notified_alerts.add(alert_key)
            elif f"{p.ip}_offline" not in self._notified_alerts:
                # Optional: Notify if a previously online printer goes offline
                # self._notified_alerts.add(f"{p.ip}_offline")
                pass

    def show_context_menu(self, pos):
        from PyQt6.QtWidgets import QMenu
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { 
                background-color: #252526; 
                border: 1px solid #3e3e42; 
                color: #cccccc;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 24px;
                border-radius: 2px;
            }
            QMenu::item:selected { 
                background-color: #094771; 
                color: #ffffff; 
            }
            QMenu::separator {
                height: 1px;
                background: #333;
                margin: 4px 8px;
            }
        """)
        
        open_web_action = menu.addAction("Open Admin Web")
        menu.addSeparator()
        copy_action = menu.addAction("Copy Row Data")
        copy_ip_action = menu.addAction("Copy IP Address")
        
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        
        if action == open_web_action:
            row = self.table.currentRow()
            if row != -1:
                ip_item = self.table.item(row, 1)
                if ip_item:
                    import webbrowser
                    webbrowser.open(f"http://{ip_item.text()}")
        elif action == copy_action:
            self.table.copy_selection()
        elif action == copy_ip_action:
            row = self.table.currentRow()
            if row != -1:
                ip_item = self.table.item(row, 1)
                if ip_item:
                    from PyQt6.QtWidgets import QApplication
                    QApplication.clipboard().setText(ip_item.text())

    def filter_table(self, text):
        text = text.lower()
        for i in range(self.table.rowCount()):
            match = False
            for j in range(self.table.columnCount()):
                item = self.table.item(i, j)
                if item and text in item.text().lower():
                    match = True
                    break
            self.table.setRowHidden(i, not match)

    def handle_selection_changed(self):
        selected = self.table.selectedItems()
        if not selected:
            self.sidebar.hide()
            return
            
        row = selected[0].row()
        ip_item = self.table.item(row, 1) # IP column
        if ip_item:
            ip = ip_item.text()
            printer = self.data_manager.printers.get(ip)
            if printer:
                self.sidebar.update_details(printer.to_dict())

    def update_stats(self):
        total = len(self.data_manager.printers)
        online = sum(1 for p in self.data_manager.printers.values() if p.is_online)
        alerts = 0
        for p in self.data_manager.printers.values():
            if p.is_online:
                for c in p.consumables:
                    if c.percentage < 15:
                        alerts += 1
                        break
        
        self.stat_total.set_value(total)
        self.stat_online.set_value(online)
        self.stat_alerts.set_value(alerts)

    def toggle_auto_refresh(self):
        if self.auto_refresh_cb.isChecked():
            self.auto_refresh_cb.setText("Auto Scan: On")
            self.refresh_timer.start(120000) # 2 mins
        else:
            self.auto_refresh_cb.setText("Auto Scan: Off")
            self.refresh_timer.stop()

    def autodetect_ip_range(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            prefix = ".".join(local_ip.split(".")[:-1])
            self.start_ip_input.setText(f"{prefix}.1")
            self.end_ip_input.setText(f"{prefix}.255")
        except Exception:
            pass

    def start_scan(self):
        self.scan_btn.setEnabled(False)
        self.progress_container.show()
        self.progress_bar.setValue(0)
        self.statusBar().showMessage("Initializing scan...")
        
        start_ip = self.start_ip_input.text().strip()
        end_ip = self.end_ip_input.text().strip()
        
        self.worker = DiscoveryWorker(start_ip, end_ip)
        self.worker.printer_found.connect(self.handle_printer_found)
        self.worker.progress.connect(lambda msg: self.statusBar().showMessage(msg))
        self.worker.progress_val.connect(self.progress_bar.setValue)
        self.worker.current_ip.connect(lambda ip: self.current_proc_label.setText(f"Active: {ip}"))
        self.worker.finished.connect(self.scan_finished)
        self.worker.start()

    def handle_printer_found(self, p_dict):
        try:
            from printscope.models.printer import Printer, Consumable
            from datetime import datetime
            
            last_seen_str = p_dict.get("last_seen")
            try:
                last_seen = datetime.fromisoformat(last_seen_str) if last_seen_str else datetime.now()
            except (ValueError, TypeError):
                last_seen = datetime.now()

            p = Printer(
                ip=p_dict["ip"], hostname=p_dict["hostname"], brand=p_dict["brand"],
                model=p_dict["model"], serial_number=p_dict["serial_number"],
                mac_address=p_dict.get("mac_address"), uptime=p_dict.get("uptime"),
                location=p_dict.get("location"),
                status=p_dict["status"], is_online=p_dict["is_online"],
                last_seen=last_seen,
                web_interface_url=p_dict["web_interface_url"]
            )
            p.consumables = [Consumable(c["name"], c["level"], c["max_capacity"]) for c in p_dict["consumables"]]
            p.history = p_dict.get("history", [])
            
            self.data_manager.add_or_update_printer(p)
            self.table.update_printer(p.to_dict())
            self.update_stats()
        except Exception as e:
            import logging
            logging.getLogger("PrintScope").error(f"Error handling found printer: {e}")

    def scan_finished(self):
        self.scan_btn.setEnabled(True)
        self.progress_container.hide()
        self.statusBar().showMessage("Discovery Complete")
        self.update_stats()

    def export_data(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export", "", "CSV Files (*.csv);;JSON Files (*.json)")
        if path:
            if path.endswith(".csv"): self.data_manager.export_csv(path)
            else: self.data_manager.export_json(path)
            QMessageBox.information(self, "Export", f"File saved: {path}")

    def apply_standard_styling(self):
        """High-End Pixel Perfect UI - Enterprise Professional."""
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1e1e1e;
                color: #cccccc;
                font-family: 'Segoe UI Variable Display', 'Segoe UI', 'Inter', Arial, sans-serif;
            }
            
            #dashboard { 
                background-color: #252526; 
                border-bottom: 1px solid #2d2d2d;
            }
            
            #ctrl_bar {
                background-color: #1e1e1e;
                border-bottom: 1px solid #2d2d2d;
            }
            
            #progress_container {
                background-color: #1e1e1e;
            }
            
            /* Custom Modern ScrollBar */
            QScrollBar:vertical {
                border: none;
                background: #1e1e1e;
                width: 10px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #3e3e42;
                min-height: 20px;
                border-radius: 5px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: #4e4e52;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            QScrollBar:horizontal {
                border: none;
                background: #1e1e1e;
                height: 10px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:horizontal {
                background: #3e3e42;
                min-width: 20px;
                border-radius: 5px;
                margin: 2px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }

            QPushButton {
                background-color: #333337;
                border: 1px solid #3e3e42;
                padding: 7px 15px;
                border-radius: 4px;
                color: #f1f1f1;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover { 
                background-color: #3e3e42; 
                border-color: #007acc; 
            }
            QPushButton:pressed { background-color: #094771; }
            
            QPushButton#scan_btn { 
                background-color: #007acc; 
                color: #ffffff;
                border: 1px solid #0097fb;
                font-weight: 600;
                letter-spacing: 0.5px;
            }
            QPushButton#scan_btn:hover { background-color: #1c97ea; border-color: #34b1ff; }
            QPushButton#scan_btn:disabled { background-color: #2d2d30; color: #555; border-color: #333; }
            
            QPushButton#report_btn {
                background-color: #2d2d30;
                border: 1px solid #3e3e42;
                color: #aeaeae;
            }
            QPushButton#report_btn:hover { color: #ffffff; border-color: #007acc; }

            QLineEdit {
                background-color: #2d2d30;
                border: 1px solid #3e3e42;
                padding: 7px 12px;
                color: #ffffff;
                border-radius: 4px;
                font-size: 13px;
                selection-background-color: #007acc;
            }
            QLineEdit:focus { border-color: #007acc; background-color: #1e1e1e; }
            
            QStatusBar {
                background-color: #007acc;
                color: #ffffff;
                font-size: 11px;
                font-weight: 500;
                padding-left: 10px;
            }
            
            QToolTip {
                background-color: #252526;
                color: #ffffff;
                border: 1px solid #3e3e42;
                padding: 6px;
                border-radius: 4px;
                font-size: 11px;
            }
            
            QLabel { color: #aeaeae; }
            
            QMenu {
                background-color: #252526;
                border: 1px solid #3e3e42;
                color: #cccccc;
                padding: 5px;
            }
            QMenu::item {
                padding: 6px 28px;
                border-radius: 3px;
                margin: 2px;
            }
            QMenu::item:selected {
                background-color: #094771;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background: #333;
                margin: 5px 10px;
            }
        """)
