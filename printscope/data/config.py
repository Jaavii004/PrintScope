import json
import os
from typing import List

class ConfigManager:
    """Manager for application settings and configuration."""
    
    DEFAULT_CONFIG = {
        "snmp_communities": ["public", "private", "community", "snmp", "admin", "printer"],
        "discovery_timeout": 2.0,
        "discovery_retries": 1,
        "auto_refresh_interval": 300, # seconds
        "ui_theme": "dark",
        "accent_color": "#2ed573"
    }

    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.config = self.DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.config.update(data)
            except Exception:
                pass

    def save(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)

    @property
    def snmp_communities(self) -> List[str]:
        return self.config.get("snmp_communities", self.DEFAULT_CONFIG["snmp_communities"])

    @snmp_communities.setter
    def snmp_communities(self, value: List[str]):
        self.config["snmp_communities"] = value

    @property
    def discovery_timeout(self) -> float:
        return self.config.get("discovery_timeout", self.DEFAULT_CONFIG["discovery_timeout"])

    @discovery_timeout.setter
    def discovery_timeout(self, value: float):
        self.config["discovery_timeout"] = value
