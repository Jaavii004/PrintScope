import sys
import asyncio
import socket
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLineEdit, QLabel, QTableWidget,
    QStatusBar, QToolBar, QFileDialog, QMessageBox,
    QSystemTrayIcon, QMenu, QProgressBar, QFrame, QStackedWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect, QUrl
from PyQt6.QtGui import QIcon, QAction, QDesktopServices

from printscope.ui.components import PrinterTable, SideNavBar, AnalyticsDashboard, DiagnosticsConsole, StatCard, DetailsSidebar
from printscope.discovery.scanner import NetworkScanner, generate_ip_range, get_local_subnets
from printscope.discovery.snmp_engine import SNMPEngine
from printscope.discovery.bonjour_engine import discover_mdns
from printscope.data.manager import PrinterManager
from printscope.data.config import ConfigManager
from printscope.ui.settings_page import SettingsPage

class DiscoveryWorker(QThread):
    """Worker thread for network discovery."""
    printer_found = pyqtSignal(dict)
    finished = pyqtSignal()
    progress = pyqtSignal(str)
    progress_val = pyqtSignal(int)
    current_ip = pyqtSignal(str)

    def __init__(self, start_ip, end_ip, config):
        super().__init__()
        self.start_ip = start_ip
        self.end_ip = end_ip
        self.config = config

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
        
        scanner = NetworkScanner(timeout=self.config.discovery_timeout, max_concurrency=60)
        snmp = SNMPEngine(timeout=self.config.discovery_timeout)
        snmp.COMMUNITIES = self.config.snmp_communities
        
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
        self.setWindowTitle("PrintScope — Enterprise Fleet Monitor")
        self.resize(1280, 760)
        self.setMinimumSize(1024, 640)
        
        self.data_manager = PrinterManager()
        self.config_manager = ConfigManager()
        
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
        main_h_layout = QHBoxLayout(central_widget)
        main_h_layout.setContentsMargins(0, 0, 0, 0)
        main_h_layout.setSpacing(0)
        
        # 1. Sidebar
        self.sidebar = SideNavBar()
        self.sidebar.nav_changed.connect(self.switch_tab)
        main_h_layout.addWidget(self.sidebar)
        
        # 2. Content Stack
        self.stack = QStackedWidget()
        main_h_layout.addWidget(self.stack)
        
        # PAGE 0: Devices
        self.devices_page = QWidget()
        self.devices_page.setStyleSheet("background: #0d0d0f;")
        devices_layout = QVBoxLayout(self.devices_page)
        devices_layout.setContentsMargins(0, 0, 0, 0)
        devices_layout.setSpacing(0)

        # PAGE 0 Header — Devices
        self.ctrl_container = QWidget()
        self.ctrl_container.setObjectName("ctrl_container")
        ctrl_layout = QHBoxLayout(self.ctrl_container)
        ctrl_layout.setContentsMargins(28, 0, 28, 0)
        ctrl_layout.setSpacing(12)
        ctrl_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.ctrl_container.setFixedHeight(64)

        # IP range
        range_lbl = QLabel("RANGE")
        range_lbl.setStyleSheet("color: #444455; font-size: 9px; font-weight: 800; letter-spacing: 1.5px;")
        ctrl_layout.addWidget(range_lbl)

        self.start_ip_input = QLineEdit("192.168.1.1")
        self.end_ip_input   = QLineEdit("192.168.1.255")
        self.start_ip_input.setFixedWidth(124)
        self.end_ip_input.setFixedWidth(124)
        arrow_lbl = QLabel("→")
        arrow_lbl.setStyleSheet("color: #444455;")
        ctrl_layout.addWidget(self.start_ip_input)
        ctrl_layout.addWidget(arrow_lbl)
        ctrl_layout.addWidget(self.end_ip_input)

        self.scan_btn = QPushButton("  ▶  RUN SCAN")
        self.scan_btn.setObjectName("scan_btn")
        self.scan_btn.setFixedHeight(36)
        self.scan_btn.setMinimumWidth(148)
        self.scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_btn.clicked.connect(self.start_scan)
        ctrl_layout.addWidget(self.scan_btn)

        ctrl_layout.addSpacing(8)

        # Search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍  Search IP, model, brand…")
        self.search_input.setMinimumWidth(220)
        self.search_input.textChanged.connect(self.filter_table)
        ctrl_layout.addWidget(self.search_input)

        ctrl_layout.addStretch()

        # Device count badge
        self.device_count_lbl = QLabel("0 devices")
        self.device_count_lbl.setStyleSheet(
            "color: #888899; background: #1a1a1e; border: 1px solid #252530;"
            " border-radius: 10px; padding: 3px 10px; font-size: 10px; font-weight: 600;"
        )
        ctrl_layout.addWidget(self.device_count_lbl)

        self.auto_refresh_cb = QPushButton("⟳  AUTO")
        self.auto_refresh_cb.setCheckable(True)
        self.auto_refresh_cb.setFixedHeight(32)
        self.auto_refresh_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self.auto_refresh_cb.clicked.connect(self.toggle_auto_refresh)
        ctrl_layout.addWidget(self.auto_refresh_cb)

        export_btn = QPushButton("📄  REPORT")
        export_btn.setFixedHeight(32)
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.setToolTip("Export HTML fleet report (Ctrl+E)")
        export_btn.clicked.connect(self.export_html_report)
        ctrl_layout.addWidget(export_btn)

        devices_layout.addWidget(self.ctrl_container)

        # Progress bar
        self.progress_container = QFrame()
        self.progress_container.setObjectName("progress_container")
        self.progress_container.setFixedHeight(24)
        prog_layout = QHBoxLayout(self.progress_container)
        prog_layout.setContentsMargins(28, 4, 28, 4)
        prog_layout.setSpacing(12)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)

        self.current_proc_label = QLabel("Ready")
        self.current_proc_label.setFixedWidth(200)
        self.current_proc_label.setStyleSheet("color: #444455; font-size: 9px; font-weight: 600;")

        prog_layout.addWidget(self.progress_bar)
        prog_layout.addWidget(self.current_proc_label)

        devices_layout.addWidget(self.progress_container)
        self.progress_container.hide()

        # Table + sidebar
        self.devices_content = QWidget()
        devices_h_layout = QHBoxLayout(self.devices_content)
        devices_h_layout.setContentsMargins(0, 0, 0, 0)
        devices_h_layout.setSpacing(0)

        self.table = PrinterTable(self.data_manager)
        self.table.itemSelectionChanged.connect(self.handle_selection_changed)
        devices_h_layout.addWidget(self.table)

        self.details_sidebar = DetailsSidebar()
        devices_h_layout.addWidget(self.details_sidebar)

        devices_layout.addWidget(self.devices_content)
        self.stack.addWidget(self.devices_page)

        # PAGE 1: Analytics
        self.analytics_page = AnalyticsDashboard(self.data_manager)
        self.stack.addWidget(self.analytics_page)

        # PAGE 2: Diagnostics — premium layout
        self.diag_page   = QWidget()
        self.diag_page.setStyleSheet("background: #0d0d0f;")
        diag_root        = QVBoxLayout(self.diag_page)
        diag_root.setContentsMargins(0, 0, 0, 0)
        diag_root.setSpacing(0)

        # Diag header bar
        diag_hdr_frame = QFrame()
        diag_hdr_frame.setFixedHeight(64)
        diag_hdr_frame.setStyleSheet("background: #141416; border-bottom: 1px solid #252530;")
        diag_hdr_layout = QHBoxLayout(diag_hdr_frame)
        diag_hdr_layout.setContentsMargins(28, 0, 28, 0)

        diag_title = QLabel("Live Diagnostics")
        diag_title.setStyleSheet(
            "color: #f0f0f5; font-size: 16px; font-weight: 800; letter-spacing: -0.3px;"
        )
        diag_sub = QLabel(" — Real-time discovery feed")
        diag_sub.setStyleSheet("color: #444455; font-size: 12px;")
        diag_hdr_layout.addWidget(diag_title)
        diag_hdr_layout.addWidget(diag_sub)
        diag_hdr_layout.addStretch()

        clear_btn = QPushButton("CLEAR")
        clear_btn.setFixedHeight(30)
        diag_hdr_layout.addWidget(clear_btn)
        diag_root.addWidget(diag_hdr_frame)

        self.console = DiagnosticsConsole()
        diag_root.addWidget(self.console)
        clear_btn.clicked.connect(self.console.clear)

        self.stack.addWidget(self.diag_page)

        # PAGE 3: Settings
        self.settings_page = SettingsPage(self.config_manager)
        self.stack.addWidget(self.settings_page)

        # Style & Interactivity
        self.apply_standard_styling()
        
        # IP Auto-detection helper
        self._init_network_intelligence()
        
        # Periodic Tasks
        from PyQt6.QtCore import QTimer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.start_scan)
        
        self.alert_timer = QTimer()
        self.alert_timer.timeout.connect(self.check_alerts)
        self.alert_timer.start(60000)
        
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self._setup_shortcuts()

    def _init_network_intelligence(self):
        """Setup logging redirection and smart network detection."""
        import logging
        class ConsoleHandler(logging.Handler):
            def __init__(self, console):
                super().__init__()
                self.console = console
            def emit(self, record):
                msg = self.format(record)
                self.console.log(record.levelname, msg)
        
        handler = ConsoleHandler(self.console)
        handler.setFormatter(logging.Formatter('%(message)s'))
        logging.getLogger("PrintScope").addHandler(handler)
        
        # Add auto-detect button to ctrl_layout
        self.auto_detect_btn = QPushButton("AUTO-DETECT RANGES")
        self.auto_detect_btn.setFixedWidth(160)
        self.auto_detect_btn.clicked.connect(self.run_auto_detect)
        # Find ctrl_layout (it's in devices_page header)
        # Actually I'll just add it to the header
        self.ctrl_container.layout().insertWidget(4, self.auto_detect_btn)

    def run_auto_detect(self):
        subnets = get_local_subnets()
        if subnets:
            self.console.log("SUCCESS", f"Auto-detected subnets: {', '.join(subnets)}")
            # For now, just set the first one
            first = subnets[0].replace("/24", "")
            prefix = ".".join(first.split(".")[:-1])
            self.start_ip_input.setText(f"{prefix}.1")
            self.end_ip_input.setText(f"{prefix}.255")
        else:
            self.console.log("WARNING", "No local subnets identified.")

    def handle_selection_changed(self):
        """Update the details sidebar when a row is selected."""
        row = self.table.currentRow()
        if row != -1:
            ip_item = self.table.item(row, 1)
            if ip_item:
                ip = ip_item.text()
                printer = self.data_manager.printers.get(ip)
                if printer:
                    self.details_sidebar.update_details(printer.to_dict())
                    self.show_sidebar()
        else:
            self.hide_sidebar()

    def show_sidebar(self):
        if not self.details_sidebar.isVisible():
            self.details_sidebar.show()
            # Smooth slide-in could be added here if needed

    def hide_sidebar(self):
        self.details_sidebar.hide()

    def switch_tab(self, index):
        if index == 1: # Analytics
            self.analytics_page.refresh_data()
        elif index == 3: # Settings
            self.config_manager.load()
            
        # Optional: Add a subtle fade-in animation
        self.stack.setCurrentIndex(index)
        anim = QPropertyAnimation(self.stack, b"windowOpacity")
        anim.setDuration(250)
        anim.setStartValue(0.7)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        anim.start()

    def show_context_menu(self, pos):
        """Premium Right-Click Command Center."""
        row = self.table.rowAt(pos.y())
        if row == -1: return
        
        ip_item = self.table.item(row, 1)
        if not ip_item: return
        ip = ip_item.text()
        printer = self.data_manager.printers.get(ip)
        
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #1a1a1c; color: white; border: 1px solid #333; } QMenu::item:selected { background-color: #007acc; }")
        
        # Actions
        actions = [
            ("🌐 Open Web Console", lambda: self.open_device_web(printer)),
            ("📡 Execute Ping Test", lambda: self.run_remote_ping(ip)),
            ("📋 Copy Serial Number", lambda: self.copy_to_clip(printer.serial_number if printer else "")),
            ("🔄 Force Deep Refresh", lambda: self.start_scan()),
            (None, None), # Separator
            ("📊 Generate PDF Insight", self.export_report)
        ]
        
        for text, func in actions:
            if text is None:
                menu.addSeparator()
            else:
                action = QAction(text, self)
                action.triggered.connect(func)
                menu.addAction(action)
                
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def open_device_web(self, printer):
        if printer and printer.ip:
            url = QUrl(f"http://{printer.ip}")
            QDesktopServices.openUrl(url)
            self.console.log("INFO", f"Opening web console for {printer.ip}...")

    def run_remote_ping(self, ip):
        self.console.log("INFO", f"Initiating ICMP Ping request to {ip}...")
        # Simple ping simulation or actual ping via subprocess
        import subprocess
        try:
            # -n 1 for windows
            res = subprocess.run(["ping", "-n", "1", ip], capture_output=True, text=True)
            if res.returncode == 0:
                self.console.log("SUCCESS", f"Ping to {ip} successful. Response received.")
            else:
                self.console.log("ERROR", f"Ping to {ip} failed. Device unreachable.")
        except Exception as e:
            self.console.log("ERROR", f"Ping execution error: {e}")

    def copy_to_clip(self, text):
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
        self.statusBar().showMessage(f"Copied: {text}", 3000)

    def show_notification(self, title, msg, icon=QSystemTrayIcon.MessageIcon.Information):
        """Show a proactive desktop notification."""
        if hasattr(self, 'tray_icon'):
            self.tray_icon.showMessage(title, msg, icon, 5000)

    def check_alerts(self):
        """Predictive Alerting Logic and Daily Checks."""
        from datetime import datetime
        for p in self.data_manager.printers.values():
            # 1. Prediction Alerts
            for c in p.consumables:
                days = p.estimate_days_remaining(c.name)
                if days is not None and days < 5:
                    self.show_notification("Proactive Supply Alert", 
                        f"Toner '{c.name}' on {p.ip} is predicted to run out in ~{days} days.",
                        QSystemTrayIcon.MessageIcon.Warning)
            
            # 2. Connectivity Alerts
            if not p.is_online and (datetime.now() - p.last_seen).total_seconds() < 300: # Recently went offline
                 self.show_notification("Connectivity Alert",
                    f"Printer {p.ip} ({p.model}) has gone offline.",
                    QSystemTrayIcon.MessageIcon.Critical)

    def setup_tray(self):
        """Setup system tray icon and menu."""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
        
        tray_menu = QMenu()
        restore_action = tray_menu.addAction("Restore PrintScope")
        restore_action.triggered.connect(self.showNormal)
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction("Exit App")
        quit_action.triggered.connect(sys.exit)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

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

    def update_stats(self):
        if hasattr(self, "analytics_page"):
            self.analytics_page.refresh_data()

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

    def _on_progress(self, msg: str):
        self.statusBar().showMessage(msg)
        if hasattr(self, "console") and msg:
            self.console.log("DEBUG", msg)

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
                ip=p_dict["ip"], hostname=p_dict.get("hostname"), brand=p_dict.get("brand"),
                model=p_dict.get("model"), serial_number=p_dict.get("serial_number"),
                mac_address=p_dict.get("mac_address"), uptime=p_dict.get("uptime"),
                location=p_dict.get("location"),
                status=p_dict.get("status", "Online"), is_online=p_dict.get("is_online", True),
                last_seen=last_seen,
                web_interface_url=p_dict.get("web_interface_url")
            )
            p.consumables = [
                Consumable(c["name"], c["level"], c["max_capacity"])
                for c in p_dict.get("consumables", [])
            ]
            p.history = p_dict.get("history", [])

            self.data_manager.add_or_update_printer(p)
            self.table.update_printer(p.to_dict())
            self.update_stats()

            supply_txt = f"{len(p.consumables)} supplies" if p.consumables else "no toner data"
            brand_model = f"{p.brand or ''} {p.model or p_dict['ip']}".strip()
            if hasattr(self, "console"):
                self.console.log("SUCCESS", f"Found: {brand_model} @ {p_dict['ip']} — {supply_txt}")

            total = len(self.data_manager.printers)
            if hasattr(self, "device_count_lbl"):
                self.device_count_lbl.setText(f"{total} device{'s' if total != 1 else ''}")
        except Exception as e:
            import logging
            logging.getLogger("PrintScope").error(f"Error handling found printer: {e}")


    def apply_standard_styling(self):
        """Apply premium enterprise dark theme — v3.0."""
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #0d0d0f;
                color: #f0f0f5;
                font-family: 'Segoe UI', 'Segoe UI Variable Display', Arial, sans-serif;
                font-size: 12px;
            }
            #ctrl_container {
                background-color: #141416;
                border-bottom: 1px solid #252530;
            }
            #progress_container { background-color: #141416; }
            QPushButton {
                background: #1a1a1e;
                border: 1px solid #252530;
                padding: 7px 16px;
                border-radius: 6px;
                color: #c0c0cc;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.5px;
            }
            QPushButton:hover { background: #212128; border-color: #35354a; color: #f0f0f5; }
            QPushButton:pressed { background: #0d0d0f; }
            QPushButton#scan_btn { background: #2ed573; color: #0d0d0f; border: none; font-weight: 700; }
            QPushButton#scan_btn:hover  { background: #48e887; }
            QPushButton#scan_btn:disabled { background: #1a2e22; color: #2a5a38; border: none; }
            QLineEdit {
                background: #1a1a1e;
                border: 1px solid #252530;
                padding: 7px 12px;
                color: #f0f0f5;
                border-radius: 6px;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #2ed573; }
            QStatusBar {
                background: #141416;
                color: #888899;
                font-size: 10px;
                font-weight: 600;
                border-top: 1px solid #252530;
            }
            QToolTip {
                background: #1a1a1e;
                color: #f0f0f5;
                border: 1px solid #35354a;
                padding: 6px 10px;
                border-radius: 6px;
                font-size: 11px;
            }
            QLabel { color: #888899; }
            QMenu {
                background: #1a1a1e;
                border: 1px solid #252530;
                color: #c0c0cc;
                padding: 6px;
                border-radius: 8px;
            }
            QMenu::item { padding: 7px 24px; border-radius: 4px; margin: 2px; }
            QMenu::item:selected { background: #212128; color: #f0f0f5; }
            QMenu::separator { height: 1px; background: #252530; margin: 4px 10px; }
            QProgressBar { background: #1a1a1e; border: none; border-radius: 3px; }
            QProgressBar::chunk { background: #2ed573; border-radius: 3px; }
        """)

    # ── Export ──────────────────────────────────────────────────────────────────

    def export_html_report(self):
        """Generate and immediately open an executive HTML fleet report."""
        import tempfile, os, webbrowser
        if not self.data_manager.printers:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "No Data", "Run a scan first to populate fleet data.")
            return
        # Save to a temp file so it always opens fresh
        tmp = os.path.join(tempfile.gettempdir(), "printscope_report.html")
        self.data_manager.export_html(tmp)
        webbrowser.open(f"file:///{tmp}")
        self.statusBar().showMessage(f"Report opened in browser — {tmp}")
        if hasattr(self, "console"):
            self.console.log("SUCCESS", f"Fleet report exported → {tmp}")

    def export_data(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export", "", "HTML Report (*.html);;CSV (*.csv);;JSON (*.json)"
        )
        if not path:
            return
        if path.endswith(".csv"):
            self.data_manager.export_csv(path)
        elif path.endswith(".json"):
            self.data_manager.export_json(path)
        else:
            self.data_manager.export_html(path)
            import webbrowser
            webbrowser.open(f"file:///{path}")
        QMessageBox.information(self, "Export", f"Saved: {path}")

    # ── Keyboard shortcuts ───────────────────────────────────────────────────────

    def _setup_shortcuts(self):
        from PyQt6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self.start_scan)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.export_html_report)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.search_input.setFocus)

    # ── Scan animation ───────────────────────────────────────────────────────────

    def _start_scan_animation(self):
        """Pulse '▶ RUN SCAN' → '⏳ Scanning…' while scan runs."""
        self._scan_anim_step = 0
        self._scan_dots = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        from PyQt6.QtCore import QTimer
        self._scan_anim_timer = QTimer(self)
        self._scan_anim_timer.timeout.connect(self._tick_scan_animation)
        self._scan_anim_timer.start(100)

    def _tick_scan_animation(self):
        dot = self._scan_dots[self._scan_anim_step % len(self._scan_dots)]
        self.scan_btn.setText(f"  {dot}  SCANNING")
        self._scan_anim_step += 1

    def _stop_scan_animation(self):
        if hasattr(self, "_scan_anim_timer"):
            self._scan_anim_timer.stop()
        self.scan_btn.setText("  ▶  RUN SCAN")

    # ── Override start_scan to add animation ────────────────────────────────────

    def start_scan(self):
        self.scan_btn.setEnabled(False)
        self.progress_container.show()
        self.progress_bar.setValue(0)
        self.statusBar().showMessage("Initializing scan…")
        self._start_scan_animation()

        start_ip = self.start_ip_input.text().strip()
        end_ip   = self.end_ip_input.text().strip()

        if hasattr(self, "console"):
            self.console.log("INFO", f"Starting discovery: {start_ip} → {end_ip}")

        self.worker = DiscoveryWorker(start_ip, end_ip, self.config_manager)
        self.worker.printer_found.connect(self.handle_printer_found)
        self.worker.progress.connect(self._on_progress)
        self.worker.progress_val.connect(self.progress_bar.setValue)
        self.worker.current_ip.connect(lambda ip: self.current_proc_label.setText(ip))
        self.worker.finished.connect(self.scan_finished)
        self.worker.start()

    def scan_finished(self):
        self._stop_scan_animation()
        self.scan_btn.setEnabled(True)
        self.progress_container.hide()
        total   = len(self.data_manager.printers)
        online  = sum(1 for p in self.data_manager.printers.values() if p.is_online)
        no_data = sum(1 for p in self.data_manager.printers.values() if not p.consumables)
        self.statusBar().showMessage(
            f"Scan complete — {total} devices | {online} online | {no_data} without toner data"
        )
        if hasattr(self, "console"):
            self.console.log(
                "SUCCESS",
                f"Scan complete: {total} devices found, {online} online, {no_data} without SNMP toner data"
            )
        if hasattr(self, "device_count_lbl"):
            self.device_count_lbl.setText(f"{total} device{'s' if total != 1 else ''}")
        self.update_stats()

