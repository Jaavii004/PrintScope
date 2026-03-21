from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
import socket
from typing import List, Dict
from printscope.models.printer import Printer

class BonjourDiscovery(ServiceListener):
    """mDNS discovery listener for printers."""
    
    def __init__(self):
        self.discovered_printers: Dict[str, Printer] = {}

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info:
            # We try to get the IP address
            ip = None
            if info.addresses:
                ip = socket.inet_ntoa(info.addresses[0])
            
            if ip:
                hostname = info.server.strip(".") if info.server else name
                model = info.properties.get(b'ty', b'').decode('utf-8') or \
                        info.properties.get(b'product', b'').decode('utf-8')
                
                printer = Printer(
                    ip=ip,
                    hostname=hostname,
                    model=model or "mDNS Printer",
                    status="Idle", # Bonjour usually implies it's online
                    is_online=True
                )
                
                # Brand guess from properties
                vendor = info.properties.get(b'usb_MFG', b'').decode('utf-8') or \
                         info.properties.get(b'MFG', b'').decode('utf-8')
                if vendor:
                    printer.brand = vendor
                
                self.discovered_printers[ip] = printer

    def update_service(self, zeroconf, type, name):
        pass

    def remove_service(self, zeroconf, type, name):
        pass

async def discover_mdns(timeout: float = 3.0) -> List[Printer]:
    """Discover printers via mDNS/Bonjour."""
    zeroconf = Zeroconf()
    listener = BonjourDiscovery()
    
    # Common printer service types
    services = ["_printer._tcp.local.", "_ipp._tcp.local.", "_ipps._tcp.local.", "_pdl-datastream._tcp.local."]
    
    browsers = [ServiceBrowser(zeroconf, service, listener) for service in services]
    
    await asyncio.sleep(timeout)
    zeroconf.close()
    
    return list(listener.discovered_printers.values())
