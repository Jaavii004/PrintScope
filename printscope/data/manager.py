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
            
            # v3.1 fields
            existing.firmware_version = printer.firmware_version or existing.firmware_version
            existing.total_pages      = printer.total_pages or existing.total_pages
            existing.memory_mb        = printer.memory_mb or existing.memory_mb
            
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
                            web_interface_url=p_data["web_interface_url"],
                            firmware_version=p_data.get("firmware_version"),
                            total_pages=p_data.get("total_pages"),
                            memory_mb=p_data.get("memory_mb")
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
        """Export an executive-grade HTML fleet report."""
        now   = datetime.now().strftime("%Y-%m-%d %H:%M")
        total = len(self.printers)
        online = sum(1 for p in self.printers.values() if p.is_online)
        pct_on = int(online / total * 100) if total else 0

        # Aggregate avg toner
        all_levels = []
        for p in self.printers.values():
            for c in p.consumables:
                all_levels.append(c.percentage)
        avg_toner = int(sum(all_levels) / len(all_levels)) if all_levels else 0

        at_risk = sum(
            1 for p in self.printers.values()
            if p.consumables and (sum(c.percentage for c in p.consumables) / len(p.consumables)) < 20
        )

        def pill_html(pct: int, name: str) -> str:
            color = "#e74c3c" if pct < 15 else ("#f39c12" if pct < 35 else "#2ed573")
            return (
                f"<div style='margin:3px 0'>"
                f"<div style='display:flex;align-items:center;gap:8px'>"
                f"<span style='color:#888;font-size:10px;width:90px;text-overflow:ellipsis;overflow:hidden;white-space:nowrap'>{name}</span>"
                f"<div style='flex:1;background:#252530;border-radius:4px;height:6px;min-width:80px'>"
                f"<div style='width:{pct}%;background:{color};height:6px;border-radius:4px'></div></div>"
                f"<span style='color:{color};font-size:10px;font-weight:700;min-width:28px'>{pct}%</span>"
                f"</div></div>"
            )

        rows_html = ""
        for p in sorted(self.printers.values(), key=lambda x: not x.is_online):
            status_col = "#2ed573" if p.is_online else "#e74c3c"
            status_txt = p.status or ("Online" if p.is_online else "Offline")

            toner_html = "".join(
                pill_html(c.percentage, c.name) for c in p.consumables[:6]
            ) if p.consumables else "<span style='color:#444;font-size:11px;font-style:italic'>No SNMP data</span>"

            rows_html += f"""
            <tr>
                <td>
                    <span style='display:inline-block;padding:3px 10px;border-radius:20px;
                        background:{status_col}22;color:{status_col};
                        font-size:10px;font-weight:700;letter-spacing:0.5px'>{status_txt}</span>
                </td>
                <td>
                    <div style='font-weight:700;color:#f0f0f5;font-size:13px'>
                        {p.brand or ''} {p.model or 'Unknown Device'}
                    </div>
                    <div style='color:#666;font-size:11px;margin-top:2px'>{p.hostname or '—'}</div>
                </td>
                <td>
                    <code style='color:#4f8ef7;font-size:12px'>{p.ip}</code><br>
                    <span style='color:#555;font-size:10px'>{p.mac_address or '—'}</span>
                </td>
                <td style='font-size:11px;color:#888'>{p.location or '—'}</td>
                <td style='font-size:11px;color:#888'>{p.serial_number or '—'}</td>
                <td style='min-width:180px'>{toner_html}</td>
                <td style='color:#555;font-size:10px'>{p.last_seen.strftime('%Y-%m-%d %H:%M') if p.last_seen else '—'}</td>
            </tr>"""

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PrintScope Fleet Report — {now}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
    background: #0d0d0f; color: #c0c0cc;
    padding: 48px; min-height: 100vh;
  }}
  .container {{ max-width: 1200px; margin: 0 auto; }}
  .header {{ display: flex; justify-content: space-between; align-items: flex-start;
             border-bottom: 1px solid #252530; padding-bottom: 28px; margin-bottom: 36px; }}
  .brand {{ font-size: 22px; font-weight: 900; color: #f0f0f5; letter-spacing: 2px; }}
  .brand span {{ color: #2ed573; }}
  .header-right {{ text-align: right; font-size: 11px; color: #555; line-height: 1.8; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(4,1fr); gap: 16px; margin-bottom: 36px; }}
  .kpi {{ background: #1a1a1e; border: 1px solid #252530; border-radius: 10px;
          padding: 20px 24px; }}
  .kpi-label {{ font-size: 9px; font-weight: 700; letter-spacing: 1.5px;
                color: #444455; text-transform: uppercase; }}
  .kpi-value {{ font-size: 28px; font-weight: 800; color: #f0f0f5; margin-top: 6px; }}
  .section-title {{ font-size: 9px; font-weight: 800; letter-spacing: 2px; color: #444455;
                    text-transform: uppercase; margin-bottom: 14px; }}
  table {{ width: 100%; border-collapse: collapse; background: #141416;
           border: 1px solid #252530; border-radius: 10px; overflow: hidden; }}
  thead tr {{ background: #1a1a1e; }}
  th {{ padding: 14px 16px; text-align: left; font-size: 9px; font-weight: 700;
        letter-spacing: 1.2px; color: #444455; text-transform: uppercase;
        border-bottom: 1px solid #252530; }}
  td {{ padding: 14px 16px; border-bottom: 1px solid #1a1a1e; vertical-align: middle; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #1f1f24; }}
  .footer {{ margin-top: 48px; text-align: center; color: #333345; font-size: 10px;
             border-top: 1px solid #1a1a1e; padding-top: 24px; }}
  code {{ font-family: 'Consolas', monospace; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div>
      <div class="brand">PRINT<span>SCOPE</span></div>
      <div style="color:#555;font-size:12px;margin-top:6px">Enterprise Fleet Intelligence Report</div>
    </div>
    <div class="header-right">
      Generated: {now}<br>
      Devices Scanned: {total}<br>
      PrintScope v3.0 Enterprise
    </div>
  </div>

  <div class="kpi-grid">
    <div class="kpi">
      <div class="kpi-label">Total Devices</div>
      <div class="kpi-value" style="color:#4f8ef7">{total}</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Online</div>
      <div class="kpi-value" style="color:#2ed573">{pct_on}%</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Avg Toner</div>
      <div class="kpi-value" style="color:#a29bfe">{avg_toner}%</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">At Risk</div>
      <div class="kpi-value" style="color:#{'e74c3c' if at_risk else '2ed573'}">{at_risk}</div>
    </div>
  </div>

  <div class="section-title">Device Inventory</div>
  <table>
    <thead>
      <tr>
        <th>Status</th>
        <th>Device</th>
        <th>IP / MAC</th>
        <th>Location</th>
        <th>Serial</th>
        <th>Supply Levels</th>
        <th>Last Seen</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>

  <div class="footer">
    Confidential · PrintScope Enterprise Fleet Report · {now}
  </div>
</div>
</body>
</html>"""

        with open(filename, "w", encoding="utf-8") as f:
            f.write(html)
