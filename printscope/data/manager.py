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
            
            # Record change in consumables for history
            if printer.consumables and printer.consumables != existing.consumables:
                existing.consumables = printer.consumables
                history_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "consumables": [
                        {"name": c.name, "level": c.level} for c in existing.consumables
                    ]
                }
                existing.history.append(history_entry)
                # Keep only last 50 entries to avoid file bloat
                if len(existing.history) > 50:
                    existing.history.pop(0)

            existing.last_seen = datetime.now()
        else:
            # New printer, add initial history
            if printer.consumables:
                printer.history = [{
                    "timestamp": datetime.now().isoformat(),
                    "consumables": [{"name": c.name, "level": c.level} for c in printer.consumables]
                }]
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
                            mac_address=p_data.get("mac_address"),
                            uptime=p_data.get("uptime"),
                            location=p_data.get("location"),
                            status=p_data["status"],
                            is_online=p_data["is_online"],
                            last_seen=datetime.fromisoformat(p_data["last_seen"]),
                            web_interface_url=p_data["web_interface_url"]
                        )
                        printer.consumables = [
                            Consumable(c["name"], c["level"], c["max_capacity"])
                            for c in p_data["consumables"]
                        ]
                        printer.history = p_data.get("history", [])
                        self.printers[ip] = printer
            except Exception as e:
                import logging
                logging.getLogger("PrintScope").error(f"Error loading data: {e}")

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

    def export_html(self, filename: str):
        """Export a professional HTML report."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total = len(self.printers)
        online = sum(1 for p in self.printers.values() if p.is_online)
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>PrintScope - Network Inventory Report</title>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; color: #333; margin: 0; padding: 40px; }}
                .report-container {{ max-width: 1000px; margin: auto; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                header {{ border-bottom: 2px solid #007acc; padding-bottom: 20px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: center; }}
                h1 {{ color: #007acc; margin: 0; font-size: 28px; }}
                .meta {{ color: #666; font-size: 14px; text-align: right; }}
                .stats-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 40px; }}
                .stat-box {{ background: #f8f9fa; padding: 20px; border-radius: 6px; border-left: 4px solid #007acc; }}
                .stat-box h3 {{ margin: 0; font-size: 12px; color: #666; text-transform: uppercase; }}
                .stat-box .val {{ font-size: 24px; font-weight: bold; color: #333; margin-top: 5px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th {{ background: #f8f9fa; text-align: left; padding: 12px; border-bottom: 2px solid #dee2e6; color: #666; font-size: 12px; text-transform: uppercase; }}
                td {{ padding: 12px; border-bottom: 1px solid #dee2e6; font-size: 14px; }}
                .status {{ font-weight: bold; }}
                .status-online {{ color: #28a745; }}
                .status-offline {{ color: #dc3545; }}
                .pill {{ background: #eee; padding: 2px 8px; border-radius: 12px; font-size: 11px; }}
            </style>
        </head>
        <body>
            <div class="report-container">
                <header>
                    <div>
                        <h1>PrintScope Pro</h1>
                        <p>Network Printer Inventory Report</p>
                    </div>
                    <div class="meta">
                        Generated on: {now}<br>
                        Exported via PrintScope IT Utility
                    </div>
                </header>
                
                <div class="stats-grid">
                    <div class="stat-box"><h3>Total Devices</h3><div class="val">{total}</div></div>
                    <div class="stat-box"><h3>Online Now</h3><div class="val">{online}</div></div>
                    <div class="stat-box" style="border-color: #28a745;"><h3>Health Score</h3><div class="val">{int(online/total*100) if total > 0 else 100}%</div></div>
                </div>

                <table>
                    <thead>
                        <tr>
                            <th>Status</th>
                            <th>Device Details</th>
                            <th>IP / MAC Address</th>
                            <th>Location / Serial</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for p in self.printers.values():
            status_cls = "status-online" if p.is_online else "status-offline"
            html += f"""
                <tr>
                    <td><span class="status {status_cls}">{p.status}</span></td>
                    <td>
                        <strong>{p.brand} {p.model}</strong><br>
                        <span style="color: #666; font-size: 12px;">{p.hostname or "No Hostname"}</span>
                    </td>
                    <td>
                        <code>{p.ip}</code><br>
                        <span class="pill">{p.mac_address or "Unknown MAC"}</span>
                    </td>
                    <td>
                        {p.location or "Unspecified Location"}<br>
                        <span style="color: #999; font-size: 11px;">{p.serial_number or "No Serial"}</span>
                    </td>
                </tr>
            """
            
        html += """
                    </tbody>
                </table>
                <footer style="margin-top: 50px; text-align: center; color: #999; font-size: 12px; border-top: 1px solid #eee; padding-top: 20px;">
                    Confidential IT Inventory Report &copy; 2026 PrintScope Autonomous Monitoring
                </footer>
            </div>
        </body>
        </html>
        """
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
