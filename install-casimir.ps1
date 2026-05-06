# install-casimir.ps1 — one-shot installer (Casimir side)
# Usage: .\install-casimir.ps1 [-WsToken <token>]
param(
    [string]$WsToken = $env:PIXEL_OFFICE_WS_TOKEN,
    [string]$WsUrl = "wss://pixel.ferdi.wtf/ws",
    [int]$Port = 8888
)
$ErrorActionPreference = "Stop"

$pixelOffice = Join-Path $HOME ".moranville-pixel-office"
$bridge = Join-Path $HOME ".moranville-bridge"

Write-Host "🌍 Moranville Pixel Office — Casimir installer" -ForegroundColor Cyan
Write-Host "  pixel-office:  $pixelOffice"
Write-Host "  bridge:        $bridge"
Write-Host "  WS hub:        $WsUrl"
Write-Host ""

if (-not $WsToken) {
    Write-Host "⚠ Pas de token WS fourni." -ForegroundColor Yellow
    Write-Host "  Demande à Ferdi de te le passer (Signal/vocal — JAMAIS par mail/Git)."
    Write-Host "  Ensuite relance: .\install-casimir.ps1 -WsToken <token>"
    Write-Host "  Ou définis: `$env:PIXEL_OFFICE_WS_TOKEN = '<token>'"
    Write-Host "  Tu peux continuer sans token: l'app marche en local-only, sans live cross-machine."
    Write-Host ""
}

# Clone / pull
if (-not (Test-Path $pixelOffice)) {
    git clone https://github.com/Moranville-be/pixel-office.git $pixelOffice
} else {
    Push-Location $pixelOffice; git pull --rebase --autostash 2>$null; Pop-Location
}
if (-not (Test-Path $bridge)) {
    git clone https://github.com/Moranville-be/bridge.git $bridge
} else {
    Push-Location $bridge; git pull --rebase --autostash 2>$null; Pop-Location
}

# Generate launcher script
$launcher = @"
# Auto-generated launcher — Moranville Pixel Office (Casimir)
`$env:PIXEL_OFFICE_WHO = "casimir"
`$env:PIXEL_OFFICE_BRIDGE = "$bridge"
`$env:PIXEL_OFFICE_PORT = "$Port"
`$env:PIXEL_OFFICE_WS_URL = "$WsUrl"
`$env:PIXEL_OFFICE_WS_TOKEN = "$WsToken"
& "$pixelOffice\start.ps1"
"@
$launcherPath = Join-Path $pixelOffice "launch-casimir.ps1"
Set-Content -Path $launcherPath -Value $launcher -Encoding UTF8

# Desktop shortcut
$shortcutPath = Join-Path $HOME "Desktop\Moranville Pixel Office.lnk"
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments = "-NoExit -ExecutionPolicy Bypass -File `"$launcherPath`""
$Shortcut.IconLocation = "imageres.dll,76"
$Shortcut.WorkingDirectory = $pixelOffice
$Shortcut.Description = "Moranville Pixel Office (Casimir side)"
$Shortcut.Save()
Write-Host "✅ Desktop shortcut: $shortcutPath" -ForegroundColor Green

# First launch
Write-Host ""
Write-Host "→ Launching for first run..." -ForegroundColor Yellow
& $launcherPath
