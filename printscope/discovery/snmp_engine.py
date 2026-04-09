import asyncio
import logging
from typing import Dict, Optional, List, Tuple
from printscope.models.printer import Printer, Consumable

logger = logging.getLogger("PrintScope")

# RFC 3805 / Printer MIB (1.3.6.1.2.1.43) - the gold standard for printer data
# Host Resources MIB (1.3.6.1.2.1.25) - device type detection
# System MIB (1.3.6.1.2.1.1) - basic device info

class SNMPEngine:
    """Robust SNMP engine with printer detection and toner level retrieval."""

    # ── Base OIDs ─────────────────────────────────────────────────────────────
    OID_SYS_DESCR      = "1.3.6.1.2.1.1.1.0"
    OID_SYS_NAME       = "1.3.6.1.2.1.1.5.0"
    OID_SYS_UPTIME     = "1.3.6.1.2.1.1.3.0"
    OID_SYS_LOCATION   = "1.3.6.1.2.1.1.6.0"
    OID_SYS_OBJECTID   = "1.3.6.1.2.1.1.2.0"   # Enterprise OID → brand hint

    # hrDevice table – walk to find printer device type
    OID_HR_DEVICE_TYPE = "1.3.6.1.2.1.25.3.2.1.2"   # .1.3.6.1.2.1.25.3.1.5 = printer
    OID_HR_DEVICE_DESC = "1.3.6.1.2.1.25.3.2.1.3"
    OID_HR_PRINTER_STATUS = "1.3.6.1.2.1.25.3.5.1.1.1"

    # Printer MIB – consumables (RFC 3805)
    OID_PRT_SUPPLY_DESC   = "1.3.6.1.2.1.43.11.1.1.6.1"   # prtMarkerSuppliesDescription
    OID_PRT_SUPPLY_MAX    = "1.3.6.1.2.1.43.11.1.1.8.1"   # prtMarkerSuppliesMaxCapacity
    OID_PRT_SUPPLY_LEVEL  = "1.3.6.1.2.1.43.11.1.1.9.1"   # prtMarkerSuppliesLevel
    OID_PRT_SUPPLY_TYPE   = "1.3.6.1.2.1.43.11.1.1.4.1"   # supply type (toner/ink/waste)
    OID_PRT_SERIAL        = "1.3.6.1.2.1.43.5.1.1.17.1"
    OID_PRT_MODEL         = "1.3.6.1.2.1.43.5.1.1.16.1"   # prtGeneralCurrentLocalization→model
    OID_PRT_INFO          = "1.3.6.1.2.1.43.5.1.1.16.2"

    # MAC address (first interface)
    OID_IF_PHYS_ADDR = "1.3.6.1.2.1.2.2.1.6.1"

    # v3.1 Hardware Intelligence
    OID_PRT_LIFE_COUNT  = "1.3.6.1.2.1.43.10.2.1.4.1.1" # Total pages printed
    OID_HR_MEMORY       = "1.3.6.1.2.1.25.2.2.0"       # Total memory (KB)
    OID_HR_SW_FIRMWARE  = "1.3.6.1.2.1.25.6.3.1.2.1"   # hrSWInstalledName (common for firmware)

    # Printer device type value from hrDeviceType
    HR_PRINTER_TYPE = "1.3.6.1.2.1.25.3.1.5"

    # Supply types to include (toner=3, ink=4, tonerCartridge=12, inkCartridge=13)
    TONER_TYPES = {3, 4, 12, 13, 16, 17, 18}

    # Brand detection strings
    BRAND_MAP = {
        "hp":       "HP",
        "hewlett":  "HP",
        "epson":    "Epson",
        "brother":  "Brother",
        "canon":    "Canon",
        "lexmark":  "Lexmark",
        "xerox":    "Xerox",
        "kyocera":  "Kyocera",
        "ricoh":    "Ricoh",
        "konica":   "Konica Minolta",
        "oki":      "OKI",
        "samsung":  "Samsung",
        "sharp":    "Sharp",
        "panasonic": "Panasonic",
        "toshiba":  "Toshiba",
        "dell":     "Dell",
        "kyo":      "Kyocera",
    }

    # Printer-related keywords in sysDescr
    PRINTER_KEYWORDS = [
        "printer", "laserjet", "officejet", "deskjet", "pixma", "lbp",
        "phaser", "workcentre", "bizhub", "aficio", "colorqube",
        "ecosys", "fs-", "taskalfa", "mfp", "multifunctional",
        "print server", "printserver", "mfc-", "hl-", "dcp-", "imagerunner",
        "imageclass", "laser", "inkjet", "colorlaserjet",
    ]

    def __init__(self, community: str = "public", port: int = 161, timeout: int = 2):
        self.community = community
        self.port = port
        self.timeout = timeout

    # ── Low-level SNMP helpers ────────────────────────────────────────────────

    async def _get(self, ip: str, oid: str) -> Optional[str]:
        """GET a single OID. Returns string value or None."""
        try:
            from pysnmp.hlapi.v3arch.asyncio import (
                SnmpEngine, CommunityData, UdpTransportTarget,
                ContextData, ObjectType, ObjectIdentity, get_cmd
            )
            engine = SnmpEngine()
            target = await UdpTransportTarget.create(
                (ip, self.port), timeout=self.timeout, retries=1
            )
            errorIndication, errorStatus, _, varBinds = await get_cmd(
                engine,
                CommunityData(self.community, mpModel=1),  # v2c
                target,
                ContextData(),
                ObjectType(ObjectIdentity(oid))
            )
            if not errorIndication and not errorStatus and varBinds:
                raw = varBinds[0][1]
                # Avoid "No Such Object/Instance" types
                if hasattr(raw, 'prettyPrint'):
                    val = raw.prettyPrint()
                    if 'noSuchObject' in val or 'noSuchInstance' in val:
                        return None
                    return val
            return None
        except Exception as e:
            logger.debug(f"SNMP GET {ip} {oid}: {e}")
            return None

    async def _walk(self, ip: str, root_oid: str) -> List[Tuple[str, str]]:
        """Walk an OID subtree. Returns list of (oid_str, value_str)."""
        results = []
        try:
            from pysnmp.hlapi.v3arch.asyncio import (
                SnmpEngine, CommunityData, UdpTransportTarget,
                ContextData, ObjectType, ObjectIdentity, bulk_cmd
            )
            engine = SnmpEngine()
            target = await UdpTransportTarget.create(
                (ip, self.port), timeout=self.timeout, retries=1
            )
            async for (errorIndication, errorStatus, _, varBindTable) in bulk_cmd(
                engine,
                CommunityData(self.community, mpModel=1),  # v2c
                target,
                ContextData(),
                0, 20,  # nonRepeaters=0, maxRepetitions=20
                ObjectType(ObjectIdentity(root_oid))
            ):
                if errorIndication or errorStatus:
                    break
                for varBind in varBindTable:
                    oid_str = str(varBind[0])
                    if not oid_str.startswith(root_oid):
                        return results  # left the subtree
                    val_str = varBind[1].prettyPrint()
                    if 'noSuchObject' not in val_str and 'noSuchInstance' not in val_str:
                        results.append((oid_str, val_str))
        except Exception as e:
            logger.debug(f"SNMP WALK {ip} {root_oid}: {e}")
        return results

    async def _walk_fallback(self, ip: str, root_oid: str) -> List[Tuple[str, str]]:
        """Fallback walk using next_cmd for devices that don't support bulk."""
        results = []
        try:
            from pysnmp.hlapi.v3arch.asyncio import (
                SnmpEngine, CommunityData, UdpTransportTarget,
                ContextData, ObjectType, ObjectIdentity, next_cmd
            )
            engine = SnmpEngine()
            target = await UdpTransportTarget.create(
                (ip, self.port), timeout=self.timeout, retries=1
            )
            current_oid = root_oid
            max_iterations = 50
            for _ in range(max_iterations):
                errorIndication, errorStatus, _, varBinds = await next_cmd(
                    engine,
                    CommunityData(self.community, mpModel=1),
                    target,
                    ContextData(),
                    ObjectType(ObjectIdentity(current_oid))
                )
                if errorIndication or errorStatus or not varBinds:
                    break
                oid_str = str(varBinds[0][0])
                if not oid_str.startswith(root_oid):
                    break
                val_str = varBinds[0][1].prettyPrint()
                results.append((oid_str, val_str))
                current_oid = oid_str
        except Exception as e:
            logger.debug(f"SNMP WALK-FALLBACK {ip} {root_oid}: {e}")
        return results

    # ── Printer detection ─────────────────────────────────────────────────────

    async def is_printer(self, ip: str, sys_descr: str) -> bool:
        """Return True if the SNMP device is likely a printer."""
        # 1. Keyword match in sysDescr
        lower = sys_descr.lower()
        if any(kw in lower for kw in self.PRINTER_KEYWORDS):
            return True

        # 2. Check hrDeviceType table for printer entry (1.3.6.1.2.1.25.3.1.5)
        types = await self._walk(ip, self.OID_HR_DEVICE_TYPE)
        if not types:
            types = await self._walk_fallback(ip, self.OID_HR_DEVICE_TYPE)
        for _, val in types:
            if self.HR_PRINTER_TYPE in val or "printer" in val.lower():
                return True

        # 3. Check Printer MIB exists (prtGeneralSerialNumber)
        serial = await self._get(ip, self.OID_PRT_SERIAL)
        if serial and serial not in ("", "noSuchObject", "noSuchInstance"):
            return True

        return False

    # Common SNMP community strings to attempt (in order of probability)
    COMMUNITIES = ["public", "private", "community", "snmp", "admin", "printer"]

    async def get_printer_details_async(self, ip: str) -> Optional[Printer]:
        """
        Try multiple SNMP community strings to retrieve printer details.
        Returns None if the device is unreachable or not a printer.
        """
        # Step 1: Try communities until we get a response
        sys_descr = None
        for community in self.COMMUNITIES:
            self.community = community
            sys_descr = await self._get(ip, self.OID_SYS_DESCR)
            if sys_descr:
                break

        if not sys_descr:
            logger.debug(f"{ip}: no SNMP response on any community string")
            return None

        logger.info(f"{ip}: SNMP OK ({self.community!r}) – {sys_descr[:60]}")

        # Step 2: Filter – is this actually a printer?
        if not await self.is_printer(ip, sys_descr):
            logger.info(f"{ip}: not a printer, skipping")
            return None

        # Step 3: Gather all OIDs in parallel
        (sys_name, serial, uptime_raw, location, mac_raw, 
         life_count, memory_kb, firmware) = await asyncio.gather(
            self._get(ip, self.OID_SYS_NAME),
            self._get(ip, self.OID_PRT_SERIAL),
            self._get(ip, self.OID_SYS_UPTIME),
            self._get(ip, self.OID_SYS_LOCATION),
            self._get(ip, self.OID_IF_PHYS_ADDR),
            self._get(ip, self.OID_PRT_LIFE_COUNT),
            self._get(ip, self.OID_HR_MEMORY),
            self._get(ip, self.OID_HR_SW_FIRMWARE)
        )

        hr_status = await self._get(ip, self.OID_HR_PRINTER_STATUS)

        # Step 4: Model from Printer MIB or sysDescr
        prt_model = await self._get(ip, self.OID_PRT_MODEL)
        model = prt_model or _clean_str(sys_descr)

        # Step 5: Brand detection
        brand = self._detect_brand(sys_descr)

        # Step 6: MAC address formatting
        mac_address = _format_mac(mac_raw)

        # Step 7: Status
        STATUS_MAP = {"1": "Other", "2": "Unknown", "3": "Idle", "4": "Printing", "5": "Warmup"}
        status = STATUS_MAP.get(hr_status or "", "Online")

        # Step 8: Uptime
        uptime = _format_uptime(uptime_raw)

        printer = Printer(
            ip=ip,
            hostname=sys_name,
            brand=brand,
            model=model,
            serial_number=serial,
            mac_address=mac_address,
            uptime=uptime,
            location=location,
            status=status,
            is_online=True,
            web_interface_url=f"http://{ip}",
            firmware_version=firmware,
            total_pages=int(life_count) if life_count and life_count.isdigit() else None,
            memory_mb=int(memory_kb) // 1024 if memory_kb and memory_kb.isdigit() else None
        )

        # Step 9: Walk consumables (with fallback)
        printer.consumables = await self._get_consumables(ip)

        logger.info(
            f"{ip}: {brand} {model} | "
            f"{len(printer.consumables)} consumables | status={status}"
        )
        return printer

    async def _get_consumables(self, ip: str) -> List[Consumable]:
        """Walk the Printer MIB supply tables and return consumable list."""
        # Try bulk first, then fallback
        desc_walk  = await self._walk(ip, self.OID_PRT_SUPPLY_DESC)
        level_walk = await self._walk(ip, self.OID_PRT_SUPPLY_LEVEL)
        max_walk   = await self._walk(ip, self.OID_PRT_SUPPLY_MAX)
        type_walk  = await self._walk(ip, self.OID_PRT_SUPPLY_TYPE)

        if not desc_walk:
            logger.debug(f"{ip}: bulk walk empty, trying next_cmd fallback")
            desc_walk  = await self._walk_fallback(ip, self.OID_PRT_SUPPLY_DESC)
            level_walk = await self._walk_fallback(ip, self.OID_PRT_SUPPLY_LEVEL)
            max_walk   = await self._walk_fallback(ip, self.OID_PRT_SUPPLY_MAX)
            type_walk  = await self._walk_fallback(ip, self.OID_PRT_SUPPLY_TYPE)

        logger.info(f"{ip}: supply walk – {len(desc_walk)} entries")

        # Build dicts keyed by the last OID digit(s)
        def _key(oid_str: str) -> str:
            return oid_str.rsplit(".", 1)[-1]

        descs  = {_key(o): v for o, v in desc_walk}
        levels = {_key(o): v for o, v in level_walk}
        maxs   = {_key(o): v for o, v in max_walk}
        types  = {_key(o): v for o, v in type_walk}

        consumables: List[Consumable] = []
        for idx, name in descs.items():
            try:
                lvl = int(levels.get(idx, "-1"))
                mx  = int(maxs.get(idx, "-1"))
            except ValueError:
                continue

            # -1 often means "not applicable" in the Printer MIB
            if lvl < 0 or mx <= 0:
                continue

            # Supply type filter – only keep toner / ink cartridges
            supply_type_str = types.get(idx, "0")
            try:
                supply_type = int(supply_type_str)
            except ValueError:
                supply_type = 0

            # Accept if type is a toner/ink type OR if type is 0 (unknown) and name hints toner
            if supply_type not in self.TONER_TYPES:
                name_lower = name.lower()
                if not any(
                    kw in name_lower
                    for kw in ["toner", "ink", "cartridge", "drum", "color", "black", "cyan", "magenta", "yellow"]
                ):
                    continue  # skip non-toner supplies (paper trays, fusers, etc.)

            consumables.append(Consumable(
                name=name.strip(),
                level=lvl,
                max_capacity=mx,
            ))

        return consumables

    def _detect_brand(self, sys_descr: str) -> Optional[str]:
        lower = sys_descr.lower()
        for key, brand in self.BRAND_MAP.items():
            if key in lower:
                return brand
        return None

    def get_printer_details(self, ip: str) -> Optional[Printer]:
        """Synchronous wrapper."""
        return asyncio.run(self.get_printer_details_async(ip))


# ── Helper functions ──────────────────────────────────────────────────────────

def _clean_str(s: str) -> str:
    """Take first meaningful line from a multi-line SNMP string."""
    return (s or "").split("\n")[0].strip()[:80]

def _format_mac(raw: Optional[str]) -> Optional[str]:
    """Convert pysnmp MAC representation to XX:XX:XX:XX:XX:XX."""
    if not raw:
        return None
    try:
        raw = raw.strip()
        if raw.startswith("0x"):
            raw = raw[2:]
        # Check if it's already hex pairs separated by spaces or colons
        raw_clean = raw.replace(":", "").replace(" ", "")
        if len(raw_clean) == 12:
            b = bytes.fromhex(raw_clean)
            return ":".join(f"{x:02x}" for x in b)
    except Exception:
        pass
    return raw

def _format_uptime(ticks_str: Optional[str]) -> Optional[str]:
    """Convert SNMP timeticks to human-readable uptime string."""
    if not ticks_str:
        return None
    try:
        # timeticks are 100ths of a second
        ticks = int(ticks_str)
        seconds = ticks // 100
        days    = seconds // 86400
        hours   = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        if days:
            return f"{days}d {hours}h {minutes}m"
        return f"{hours}h {minutes}m"
    except Exception:
        return ticks_str
