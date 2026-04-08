import asyncio
import socket
from printscope.discovery.bonjour_engine import discover_mdns
from printscope.discovery.scanner import NetworkScanner, generate_ip_range
from printscope.discovery.snmp_engine import SNMPEngine

async def main():
    print("--- Diagnostic Scan V2 ---")
    
    # Test mDNS (AsyncZeroconf)
    print("\n1. Testing mDNS (Bonjour with AsyncZeroconf)...")
    try:
        printers = await discover_mdns(5.0)
        print(f"   Found {len(printers)} printers via mDNS:")
        for p in printers:
            print(f"   - {p.ip} ({p.hostname}) - Model: {p.model}")
    except Exception as e:
        print(f"   mDNS Error: {e}")

    # Test Port Scan (Detect Local Net)
    print("\n2. Testing Port Scan (Local Subnet)...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        prefix = ".".join(local_ip.split(".")[:-1])
        print(f"   Detected local IP: {local_ip}, scanning {prefix}.1-30")
        
        scanner = NetworkScanner(timeout=1.5, max_concurrency=40)
        test_ips = [f"{prefix}.{i}" for i in range(1, 31)]
        
        results = await scanner.scan_range(test_ips)
        print(f"   Found {len(results)} candidate IPs:")
        for ip in results:
            print(f"   - {ip}")
            
        # Test SNMP enrichment
        if results:
            print(f"\n3. Testing SNMP on {results[0]}...")
            snmp = SNMPEngine()
            details = await snmp.get_printer_details_async(results[0])
            if details:
                print(f"   Model: {details.model}, Status: {details.status}")
                print(f"   Consumables: {len(details.consumables)}")
            else:
                print("   SNMP failed (no response or wrong community)")

    except Exception as e:
        print(f"   Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
