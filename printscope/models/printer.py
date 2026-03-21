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
    status: str = "Unknown"
    is_online: bool = False
    consumables: List[Consumable] = field(default_factory=list)
    last_seen: datetime = field(default_factory=datetime.now)
    web_interface_url: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "ip": self.ip,
            "hostname": self.hostname,
            "brand": self.brand,
            "model": self.model,
            "serial_number": self.serial_number,
            "status": self.status,
            "is_online": self.is_online,
            "consumables": [
                {"name": c.name, "level": c.level, "max_capacity": c.max_capacity, "percentage": c.percentage}
                for c in self.consumables
            ],
            "last_seen": self.last_seen.isoformat(),
            "web_interface_url": self.web_interface_url
        }
