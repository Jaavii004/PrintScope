import json
import csv
import os
from typing import List, Dict
from datetime import datetime
from printscope.models.printer import Printer, Consumable

class PrinterManager:
    """Manager for data persistence and exporting."""
    
    def __init__(self, data_file: str = "discovered_printers.json"):
        self.data_file = data_file
        self.printers: Dict[str, Printer] = {}
        self.load()

    def add_or_update_printer(self, printer: Printer):
        """Add a new printer or update an existing one."""
        if printer.ip in self.printers:
            existing = self.printers[printer.ip]
            # Update only if new data is richer
            existing.hostname = printer.hostname or existing.hostname
            existing.model = printer.model or existing.model
            existing.brand = printer.brand or existing.brand
            existing.serial_number = printer.serial_number or existing.serial_number
            existing.status = printer.status
            existing.is_online = printer.is_online
            existing.consumables = printer.consumables or existing.consumables
            existing.last_seen = datetime.now()
        else:
            self.printers[printer.ip] = printer
        self.save()

    def save(self):
        """Save discovered printers to JSON."""
        data = {ip: p.to_dict() for ip, p in self.printers.items()}
        with open(self.data_file, 'w') as f:
            json.dump(data, f, indent=4)

    def load(self):
        """Load printers from JSON."""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    for ip, p_data in data.items():
                        printer = Printer(
                            ip=p_data["ip"],
                            hostname=p_data["hostname"],
                            brand=p_data["brand"],
                            model=p_data["model"],
                            serial_number=p_data["serial_number"],
                            status=p_data["status"],
                            is_online=p_data["is_online"],
                            last_seen=datetime.fromisoformat(p_data["last_seen"]),
                            web_interface_url=p_data["web_interface_url"]
                        )
                        printer.consumables = [
                            Consumable(c["name"], c["level"], c["max_capacity"])
                            for c in p_data["consumables"]
                        ]
                        self.printers[ip] = printer
            except Exception as e:
                print(f"Error loading data: {e}")

    def export_csv(self, filename: str):
        """Export to CSV."""
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["IP", "Hostname", "Brand", "Model", "Serial", "Status", "Online", "Last Seen"])
            for p in self.printers.values():
                writer.writerow([
                    p.ip, p.hostname, p.brand, p.model, p.serial_number, 
                    p.status, p.is_online, p.last_seen.isoformat()
                ])

    def export_json(self, filename: str):
        """Export to JSON."""
        data = [p.to_dict() for p in self.printers.values()]
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)
