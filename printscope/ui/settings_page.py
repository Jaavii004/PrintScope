from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFrame, QScrollArea,
    QTextEdit, QDoubleSpinBox, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt
from printscope.ui.components import (
    BG_BASE, BG_CARD, BORDER, TEXT_PRIMARY, TEXT_SECONDARY, 
    ACCENT, FONT_MAIN, TEXT_MUTED
)

class SettingsPage(QWidget):
    """Premium Settings Dashboard v3.1"""

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.setStyleSheet(f"background: {BG_BASE};")

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 36, 40, 36)
        root.setSpacing(28)

        # Header
        h_lbl = QLabel("System Settings")
        h_lbl.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 26px; font-weight: 800; letter-spacing: -0.5px;"
        )
        sub_lbl = QLabel("Manage SNMP protocols, discovery engine parameters, and UI preferences.")
        sub_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        root.addWidget(h_lbl)
        root.addWidget(sub_lbl)

        # Scroll area for settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self.layout = QVBoxLayout(container)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(24)

        # 1. SNMP COMMUNITIES
        snmp_frame = self._create_section("SNMP PROTOCOL", "Define community strings for network discovery.")
        self.communities_input = QTextEdit()
        self.communities_input.setPlaceholderText("Enter one community string per line (e.g., public, private)")
        self.communities_input.setStyleSheet(f"""
            QTextEdit {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 8px;
                color: {TEXT_PRIMARY};
                padding: 12px;
                font-family: 'Consolas';
                font-size: 13px;
            }}
        """)
        self.communities_input.setPlainText("\n".join(self.config_manager.snmp_communities))
        snmp_frame.layout().addWidget(self.communities_input)
        self.layout.addWidget(snmp_frame)

        # 2. DISCOVERY PARAMETERS
        disc_frame = self._create_section("DISCOVERY ENGINE", "Optimize speed vs reliability for network scans.")
        disc_layout = QGridLayout()
        disc_layout.setSpacing(20)

        # Timeout
        t_lbl = QLabel("SNMP Timeout (sec)")
        t_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        self.timeout_spinner = QDoubleSpinBox()
        self.timeout_spinner.setRange(0.5, 10.0)
        self.timeout_spinner.setSingleStep(0.5)
        self.timeout_spinner.setValue(self.config_manager.discovery_timeout)
        self.timeout_spinner.setStyleSheet(self._spinbox_style())
        disc_layout.addWidget(t_lbl, 0, 0)
        disc_layout.addWidget(self.timeout_spinner, 0, 1)

        # Auto-refresh
        r_lbl = QLabel("Auto-Refresh (min)")
        r_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        self.refresh_spinner = QDoubleSpinBox()
        self.refresh_spinner.setRange(1, 60)
        self.refresh_spinner.setSingleStep(5)
        self.refresh_spinner.setValue(self.config_manager.config.get("auto_refresh_interval", 300) / 60)
        self.refresh_spinner.setStyleSheet(self._spinbox_style())
        disc_layout.addWidget(r_lbl, 1, 0)
        disc_layout.addWidget(self.refresh_spinner, 1, 1)

        disc_frame.layout().addLayout(disc_layout)
        self.layout.addWidget(disc_frame)

        # 3. SAVE BUTTON
        self.save_btn = QPushButton("APPLY SETTINGS")
        self.save_btn.setFixedHeight(45)
        self.save_btn.setFixedWidth(200)
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT};
                color: {BG_BASE};
                font-weight: 800;
                font-size: 13px;
                border: none;
                border-radius: 10px;
                margin-top: 10px;
            }}
            QPushButton:hover {{
                background: #48e887;
            }}
            QPushButton:pressed {{
                background: #25bb62;
            }}
        """)
        self.save_btn.clicked.connect(self.save_settings)
        self.layout.addWidget(self.save_btn)

        self.layout.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll)

    def _create_section(self, title, subtitle):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(12)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; font-weight: 800; letter-spacing: 2px;")
        s_lbl = QLabel(subtitle)
        s_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        
        layout.addWidget(t_lbl)
        layout.addWidget(s_lbl)
        return frame

    def _spinbox_style(self):
        return f"""
            QDoubleSpinBox {{
                background: {BG_BASE};
                border: 1px solid {BORDER};
                border-radius: 6px;
                color: {TEXT_PRIMARY};
                padding: 6px 10px;
                font-size: 13px;
                min-width: 80px;
            }}
        """

    def save_settings(self):
        # 1. Update Communities
        text = self.communities_input.toPlainText().strip()
        communities = [c.strip() for c in text.split("\n") if c.strip()]
        self.config_manager.snmp_communities = communities if communities else ["public"]

        # 2. Update Discovery
        self.config_manager.discovery_timeout = self.timeout_spinner.value()
        self.config_manager.config["auto_refresh_interval"] = self.refresh_spinner.value() * 60

        self.config_manager.save()
        
        # Show feedback (could be a notification)
        self.save_btn.setText("✓ SETTINGS SAVED")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self.save_btn.setText("APPLY SETTINGS"))
