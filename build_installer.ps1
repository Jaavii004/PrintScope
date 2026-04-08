# Build Script for PrintScope (Windows Installer)

Write-Host "Paso 1/4: Instalando dependencias de Python..." -ForegroundColor Cyan
pip install -r requirements.txt
pip install pyinstaller

Write-Host "`nPaso 2/4: Empaquetando aplicacion con PyInstaller..." -ForegroundColor Cyan
pyinstaller --clean --noconfirm --onedir --windowed --name "PrintScope" `
    --collect-all "pysnmp" `
    --collect-all "pyasn1" `
    --collect-all "pysmi" `
    --collect-all "pysnmpcrypto" `
    --collect-all "zeroconf" `
    --copy-metadata "pysnmp" `
    --add-data "discovered_printers.json;." `
    "run.py"

Write-Host "`nPaso 3/4: Verificando Inno Setup..." -ForegroundColor Cyan
$isccPath = ""
$potentialPaths = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
    "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe"
)

foreach ($path in $potentialPaths) {
    if (Test-Path $path) {
        $isccPath = $path
        break
    }
}

if ($isccPath -eq "") {
    Write-Host "ERROR: No se pudo encontrar ISCC.exe. Por favor, instala Inno Setup 6." -ForegroundColor Red
    exit 1
}

Write-Host "ISCC encontrado en: $isccPath" -ForegroundColor Green

Write-Host "`nPaso 4/4: Creando instalador (Inno Setup)..." -ForegroundColor Cyan
& $isccPath "printscope.iss"

Write-Host "`nPROCESO COMPLETADO!" -ForegroundColor Green
Write-Host "El instalador se encuentra en: Output\PrintScope_Setup.exe" -ForegroundColor Yellow
