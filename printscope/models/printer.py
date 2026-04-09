from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime

@dataclass
class Consumable:
    name: str
    level: int  # Current level (e.g., 0-100 or actual value)
    max_capacity: int
    unit: str = "percent"
    
    @property
    def percentage(self) -> int:
        if self.max_capacity > 0:
            return min(100, max(0, int((self.level / self.max_capacity) * 100)))
        return self.level if self.unit == "percent" else 0

@dataclass
class Printer:
    ip: str
    hostname: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    mac_address: Optional[str] = None
    uptime: Optional[str] = None
    location: Optional[str] = None
    status: str = "Unknown"
    is_online: bool = False
    consumables: List[Consumable] = field(default_factory=list)
    history: List[Dict] = field(default_factory=list) # Snapshot of levels over time
    last_seen: datetime = field(default_factory=datetime.now)
    web_interface_url: Optional[str] = None
    
    # v3.1 Hardware Intelligence
    firmware_version: Optional[str] = None
    total_pages: Optional[int] = None
    memory_mb: Optional[int] = None

    def estimate_days_remaining(self, consumable_name: str) -> Optional[int]:
        """Simple linear regression to estimate days remaining for a consumable."""
        if len(self.history) < 3:
            return None # Need more data for prediction
            
        relevant_history = []
        for h in self.history:
            for c in h.get("consumables", []):
                if c["name"] == consumable_name:
                    ts = datetime.fromisoformat(h["timestamp"]).timestamp()
                    relevant_history.append((ts, c["level"]))
                    
        if len(relevant_history) < 3:
            return None
            
        # Sort by timestamp
        relevant_history.sort()
        
        # Calculate consumption rate (unit per second)
        # Simplified: (last_level - first_level) / (last_ts - first_ts)
        first_ts, first_lvl = relevant_history[0]
        last_ts, last_lvl = relevant_history[-1]
        
        duration = last_ts - first_ts
        if duration <= 0:
            return None
            
        usage = first_lvl - last_lvl
        if usage <= 0:
            return None # Level is increasing or stable
            
        rate_per_sec = usage / duration
        seconds_left = last_lvl / rate_per_sec
        return int(seconds_left / 86400) # Convert to days

    def to_dict(self) -> Dict:
        return {
            "ip": self.ip,
            "hostname": self.hostname,
            "brand": self.brand,
            "model": self.model,
            "serial_number": self.serial_number,
            "mac_address": self.mac_address,
            "uptime": self.uptime,
            "location": self.location,
            "status": self.status,
            "is_online": self.is_online,
            "consumables": [
                {
                    "name": c.name, 
                    "level": c.level, 
                    "max_capacity": c.max_capacity, 
                    "percentage": c.percentage,
                    "est_days": self.estimate_days_remaining(c.name)
                }
                for c in self.consumables
            ],
            "history": self.history,
            "last_seen": self.last_seen.isoformat(),
            "web_interface_url": self.web_interface_url,
            "firmware_version": self.firmware_version,
            "total_pages": self.total_pages,
            "memory_mb": self.memory_mb
        }
