import asyncio
import socket
from typing import List, Set

class NetworkScanner:
    """Async scanner to find devices on the network with open printer-related ports."""
    
    PRINTER_PORTS = [80, 443, 515, 631, 9100]
    
    def __init__(self, timeout: float = 1.0):
        self.timeout = timeout

    async def check_port(self, ip: str, port: int) -> bool:
        """Check if a specific port is open on an IP address."""
        try:
            conn = asyncio.open_connection(ip, port)
            _, writer = await asyncio.wait_for(conn, timeout=self.timeout)
            writer.close()
            await writer.wait_closed()
            return True
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            return False

    async def is_printer_candidate(self, ip: str) -> bool:
        """Check if any common printer ports are open."""
        tasks = [self.check_port(ip, port) for port in self.PRINTER_PORTS]
        results = await asyncio.gather(*tasks)
        return any(results)

    async def scan_range(self, ip_range: List[str]) -> List[str]:
        """Scan a list of IP addresses and return those that look like printers."""
        tasks = [self.is_printer_candidate(ip) for ip in ip_range]
        results = await asyncio.gather(*tasks)
        return [ip for ip, is_printer in zip(ip_range, results) if is_printer]

def generate_ip_range(start_ip: str, end_ip: str) -> List[str]:
    """Generate a list of IPs between start and end (inclusive)."""
    import ipaddress
    start = ipaddress.IPv4Address(start_ip)
    end = ipaddress.IPv4Address(end_ip)
    return [str(ipaddress.IPv4Address(ip)) for ip in range(int(start), int(end) + 1)]
