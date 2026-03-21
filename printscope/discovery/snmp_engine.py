import asyncio
from pysnmp.entity.rfc3413.oneliner import cmdgen
from typing import Dict, Optional, List
from printscope.models.printer import Printer, Consumable

class SNMPEngine:
    """SNMP engine to retrieve detailed printer information."""
    
    # OIDs from research
    OIDS = {
        "sysDescr": "1.3.6.1.2.1.1.1.0",
        "sysName": "1.3.6.1.2.1.1.5.0",
        "hrDeviceDescr": "1.3.6.1.2.1.25.3.2.1.3.1",
        "hrPrinterStatus": "1.3.6.1.2.1.25.3.5.1.1.1",
        "prtGeneralSerialNumber": "1.3.6.1.2.1.43.5.1.1.17.1",
    }
    
    # Tables
    SUPPLY_DESC_OID = "1.3.6.1.2.1.43.11.1.1.6.1"
    SUPPLY_MAX_OID = "1.3.6.1.2.1.43.11.1.1.8.1"
    SUPPLY_LEVEL_OID = "1.3.6.1.2.1.43.11.1.1.9.1"

    def __init__(self, community="public", port=161, timeout=2):
        self.community = community
        self.port = port
        self.timeout = timeout
        self.cmd_gen = cmdgen.CommandGenerator()

    def get_oid(self, ip: str, oid: str) -> Optional[str]:
        """Fetch a single OID value."""
        error_indication, error_status, error_index, var_binds = self.cmd_gen.getCmd(
            cmdgen.CommunityData(self.community),
            cmdgen.UdpTransportTarget((ip, self.port), timeout=self.timeout, retries=1),
            oid
        )
        if not error_indication and not error_status:
            for _, val in var_binds:
                return str(val)
        return None

    def get_table(self, ip: str, root_oid: str) -> Dict[str, str]:
        """Fetch a table (nextCmd)."""
        error_indication, error_status, error_index, var_bind_table = self.cmd_gen.nextCmd(
            cmdgen.CommunityData(self.community),
            cmdgen.UdpTransportTarget((ip, self.port), timeout=self.timeout, retries=1),
            root_oid
        )
        results = {}
        if not error_indication and not error_status:
            for var_binds in var_bind_table:
                for oid, val in var_binds:
                    if str(oid).startswith(root_oid):
                        results[str(oid)] = str(val)
                    else:
                        break
        return results

    def get_printer_details(self, ip: str) -> Optional[Printer]:
        """Fetch all relevant printer details for an IP."""
        desc = self.get_oid(ip, self.OIDS["sysDescr"])
        if not desc:
            return None # Not responding to SNMP

        hostname = self.get_oid(ip, self.OIDS["sysName"])
        device_desc = self.get_oid(ip, self.OIDS["hrDeviceDescr"])
        status_code = self.get_oid(ip, self.OIDS["hrPrinterStatus"])
        serial = self.get_oid(ip, self.OIDS["prtGeneralSerialNumber"])

        # Translate status
        status_map = {"1": "Other", "2": "Unknown", "3": "Idle", "4": "Printing", "5": "Warmup"}
        status = status_map.get(status_code, "Unknown")

        printer = Printer(
            ip=ip,
            hostname=hostname,
            model=device_desc or desc,
            serial_number=serial,
            status=status,
            is_online=True
        )

        # Consumables
        names = self.get_table(ip, self.SUPPLY_DESC_OID)
        maxes = self.get_table(ip, self.SUPPLY_MAX_OID)
        levels = self.get_table(ip, self.SUPPLY_LEVEL_OID)

        for oid, name in names.items():
            suffix = oid.split(".")[-1]
            max_val = maxes.get(f"{self.SUPPLY_MAX_OID}.{suffix}", "0")
            level_val = levels.get(f"{self.SUPPLY_LEVEL_OID}.{suffix}", "0")
            
            try:
                printer.consumables.append(Consumable(
                    name=name,
                    level=int(level_val),
                    max_capacity=int(max_val)
                ))
            except ValueError:
                continue

        # Guess brand based on description
        lower_desc = (desc or "").lower()
        if "hp " in lower_desc: printer.brand = "HP"
        elif "epson" in lower_desc: printer.brand = "Epson"
        elif "brother" in lower_desc: printer.brand = "Brother"
        elif "canon" in lower_desc: printer.brand = "Canon"
        elif "lexmark" in lower_desc: printer.brand = "Lexmark"
        elif "xerox" in lower_desc: printer.brand = "Xerox"

        printer.web_interface_url = f"http://{ip}"
        
        return printer
