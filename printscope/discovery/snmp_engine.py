import asyncio
from pysnmp.hlapi.v3arch import (
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData, 
    ObjectType, ObjectIdentity, get_cmd, next_cmd
)
from typing import Dict, Optional, List, Tuple
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
        "sysUpTime": "1.3.6.1.2.1.1.3.0",
        "sysLocation": "1.3.6.1.2.1.1.6.0",
        "ifPhysAddress": "1.3.6.1.2.1.2.2.1.6.1", # Usually first interface
    }
    
    # Tables
    SUPPLY_DESC_OID = "1.3.6.1.2.1.43.11.1.1.6.1"
    SUPPLY_MAX_OID = "1.3.6.1.2.1.43.11.1.1.8.1"
    SUPPLY_LEVEL_OID = "1.3.6.1.2.1.43.11.1.1.9.1"

    def __init__(self, community="public", port=161, timeout=2):
        self.community = community
        self.port = port
        self.timeout = timeout
        self.snmp_engine = SnmpEngine()

    def _run_async(self, coro):
        """Helper to run a coroutine in the current thread's loop or a new one."""
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                # This is tricky: if the loop is already running, we can't block.
                # But SNMPEngine's public API is synchronous.
                # In DiscoveryWorker, we call this OUTSIDE of run_until_complete,
                # so the loop exists but is NOT running.
                return loop.run_until_complete(coro)
        except RuntimeError:
            pass
        return asyncio.run(coro)

    def get_oid(self, ip: str, oid: str) -> Optional[str]:
        """Fetch a single OID value."""
        return self._run_async(self._get_oid_async(ip, oid))  # type: ignore

    async def _get_oid_async(self, ip: str, oid: str) -> Optional[str]:
        try:
            error_indication, error_status, error_index, var_binds = await get_cmd(
                self.snmp_engine,
                CommunityData(self.community),
                await UdpTransportTarget.create((ip, self.port), timeout=self.timeout, retries=1),
                ContextData(),
                ObjectType(ObjectIdentity(oid))
            )
            
            if not error_indication and not error_status:
                for _, val in var_binds:
                    return str(val)
        except Exception as e:
            print(f"SNMP get error for {ip} {oid}: {e}")
        return None

    def get_table(self, ip: str, root_oid: str) -> Dict[str, str]:
        """Fetch a table (next_cmd)."""
        return self._run_async(self._walk_subtree_async(ip, root_oid)) or {}  # type: ignore

    async def _walk_subtree_async(self, ip: str, root_oid: str) -> List[Tuple[str, str]]:
        """Walk an SNMP subtree and return all varbinds."""
        results = []
        target_oid = root_oid
        
        while True:
            try:
                errorIndication, errorStatus, errorIndex, varBinds = await next_cmd(
                    self.snmp_engine,
                    CommunityData(self.community, mpModel=1), # Support SNMP v2c
                    await UdpTransportTarget.create((ip, self.port), timeout=1, retries=1),
                    ContextData(),
                    ObjectType(ObjectIdentity(target_oid))
                )
                
                if errorIndication or errorStatus:
                    break
                    
                # next_cmd returns a list of varBindTables, each is a list of varBinds
                if not varBinds or not varBinds[0]:
                    break
                    
                varBind = varBinds[0][0]
                res_oid = str(varBind[0])
                res_val = str(varBind[1])
                
                # Check if we are still in the same subtree
                if not res_oid.startswith(root_oid):
                    break
                    
                results.append((res_oid, res_val))
                target_oid = res_oid # Continue from here
                
            except Exception:
                break
                
        return results

    async def get_printer_details_async(self, ip: str) -> Optional[Printer]:
        """Fetch details from a printer via SNMP asynchronously."""
        import logging
        logger = logging.getLogger("PrintScope")
        
        desc = await self._get_oid_async(ip, self.OIDS["sysDescr"])
        if not desc:
            logger.info(f"Device {ip} did not respond to sysDescr SNMP")
            return None # Not responding to SNMP

        logger.info(f"Found SNMP device at {ip}: {desc}")
        
        hostname = await self._get_oid_async(ip, self.OIDS["sysName"])
        device_desc = await self._get_oid_async(ip, self.OIDS["hrDeviceDescr"])
        status_code = await self._get_oid_async(ip, self.OIDS["hrPrinterStatus"])
        serial = await self._get_oid_async(ip, self.OIDS["prtGeneralSerialNumber"])
        uptime_ticks = await self._get_oid_async(ip, self.OIDS["sysUpTime"])
        location = await self._get_oid_async(ip, self.OIDS["sysLocation"])
        mac_raw = await self._get_oid_async(ip, self.OIDS["ifPhysAddress"])

        # Format MAC address (OctetString to XX:XX:XX:XX:XX:XX)
        mac_address = None
        if mac_raw:
            # pysnmp may return it as hex string or binary
            try:
                if mac_raw.startswith('0x'):
                    mac_bytes = bytes.fromhex(mac_raw[2:])
                else:
                    mac_bytes = mac_raw.encode('ascii') # or already bytes
                mac_address = ':'.join(['{:02x}'.format(b) for b in mac_bytes])
            except Exception:
                mac_address = mac_raw # Fallback

        # Format Uptime (Ticks to simple string)
        uptime = str(uptime_ticks) if uptime_ticks else "N/A"

        # Translate status
        status_map = {"1": "Other", "2": "Unknown", "3": "Idle", "4": "Printing", "5": "Warmup"}
        status = status_map.get(status_code or "", "Unknown")

        printer = Printer(
            ip=ip,
            hostname=hostname,
            model=device_desc or desc,
            serial_number=serial,
            mac_address=mac_address,
            uptime=uptime,
            location=location,
            status=status,
            is_online=True
        )

        # Get consumables by walking tables
        logger.info(f"Walking supplies tables for {ip}...")
        names_walk = await self._walk_subtree_async(ip, self.SUPPLY_DESC_OID)
        levels_walk = await self._walk_subtree_async(ip, self.SUPPLY_LEVEL_OID)
        max_walk = await self._walk_subtree_async(ip, self.SUPPLY_MAX_OID)
        
        logger.info(f"Walked {len(names_walk)} supply names for {ip}")
        
        # Extract indices and match values
        names_dict = {oid.split('.')[-1]: val for oid, val in names_walk}
        levels_dict = {oid.split('.')[-1]: val for oid, val in levels_walk}
        max_dict = {oid.split('.')[-1]: val for oid, val in max_walk}
        
        for idx in names_dict:
            name = names_dict[idx]
            level = int(levels_dict.get(idx, -1))
            mcap = int(max_dict.get(idx, -1))
            
            # Filter out irrelevant markers
            if level == -1 or mcap == -1: continue
            
            printer.consumables.append(Consumable(name, level, mcap))

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

    def get_printer_details(self, ip: str) -> Optional[Printer]:
        """Synchronous wrapper for get_printer_details_async."""
        return self._run_async(self.get_printer_details_async(ip))
