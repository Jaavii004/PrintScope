# PrintScope

A professional-grade network scanning application specifically focused on detecting and monitoring network printers.

## Features

- **Multi-protocol Discovery**: Automatically detects printers using SNMP and mDNS/Bonjour.
- **Deep Monitoring**: Retrieves real-time status and ink/toner levels via SNMP.
- **Async Scanning**: High-performance asynchronous network scanning for large IP ranges.
- **Modern UI**: Clean PyQt6 interface with sortable tables and color-coded status indicators.
- **Persistence**: Automatically saves discovered devices for future monitoring.
- **Export**: Export scan results to CSV and JSON formats.
- **Web Interface**: Quick access to printer web configuration pages via context menu.
- **Auto-Refresh**: Periodic polling to keep printer status up to date.

## Installation

1. **Requirements**: Python 3.8+
2. **Setup**:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

Executet the main script:
```bash
python -m printscope.main
```

## Creating the Windows Installer

To create a professional `.exe` installer for Windows:

1. **Install Inno Setup 6**: Download and install it from [jrsoftware.org](https://jrsoftware.org/isdl.php).
2. **Run the Build Script**:
   ```powershell
   ./build_installer.ps1
   ```
   This script will:
   - Install required Python dependencies.
   - Bundle the application with PyInstaller.
   - Compile the Windows installer using Inno Setup.

The resulting installer will be saved in `Output\PrintScope_Setup.exe`.

## How it Works

1. **IP Range Scan**: The app first performs an asynchronous port check on the specified IP range to identify potential network devices.
2. **mDNS Discovery**: Simultaneously, it listens for Bonjour advertisements on the local network.
3. **SNMP Querying**: For each found device, PrintScope queries standard Printer MIB OIDs to fetch brand, model, serial number, and consumable levels.
4. **Real-time Updates**: The status is reflected in the UI with color indicators (Green=Idle, Blue=Printing, Red=Error/Offline).

## Technical Details

- **Language**: Python 3
- **GUI Framework**: PyQt6
- **Networking**: `asyncio`, `socket`
- **Discovery**: `pysnmp-lextudio`, `zeroconf`
- **Data**: JSON persistence for discovered devices.

## License

MIT License. See `LICENSE` for details.
