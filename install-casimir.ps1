# install-casimir.ps1 — one-shot installer for the Casimir-side pixel-office.
# Run this once on Windows. It will:
#   1. Clone (or pull) Moranville-be/pixel-office and Moranville-be/bridge
#   2. Create a desktop shortcut "Moranville Pixel Office.lnk"
#   3. Launch the pixel-office for the first time (port 8888 by default)
#
# Usage:
#   PowerShell> .\install-casimir.ps1
#
# Environment overrides:
#   $env:PIXEL_OFFICE_DIR  → install root (default: $HOME\.moranville-pixel-office)
#   $env:BRIDGE_DIR        → bridge clone  (default: $HOME\.moranville-bridge)
#   $env:PIXEL_OFFICE_PORT → port (default: 8888)

$ErrorActionPreference = "Stop"

# ─── Paths ───
$pixelOffice = if ($env:PIXEL_OFFICE_DIR) { $env:PIXEL_OFFICE_DIR } else { Join-Path $HOME ".moranville-pixel-office" }
$bridge      = if ($env:BRIDGE_DIR)        { $env:BRIDGE_DIR }        else { Join-Path $HOME ".moranville-bridge" }
$port        = if ($env:PIXEL_OFFICE_PORT) { $env:PIXEL_OFFICE_PORT } else { "8888" }

Write-Host "🌍 Moranville Pixel Office — Casimir side installer" -ForegroundColor Cyan
Write-Host ""
Write-Host "  pixel-office: $pixelOffice"
Write-Host "  bridge:       $bridge"
Write-Host "  port:         $port"
Write-Host ""

# ─── Clone or pull ───
if (-not (Test-Path $pixelOffice)) {
    Write-Host "→ Cloning Moranville-be/pixel-office..." -ForegroundColor Yellow
    git clone https://github.com/Moranville-be/pixel-office.git $pixelOffice
} else {
    Write-Host "→ Pulling pixel-office latest..." -ForegroundColor Yellow
    Push-Location $pixelOffice
    git pull --rebase --autostash 2>$null
    Pop-Location
}

if (-not (Test-Path $bridge)) {
    Write-Host "→ Cloning Moranville-be/bridge..." -ForegroundColor Yellow
    git clone https://github.com/Moranville-be/bridge.git $bridge
} else {
    Write-Host "→ Pulling bridge latest..." -ForegroundColor Yellow
    Push-Location $bridge
    git pull --rebase --autostash 2>$null
    Pop-Location
}

# ─── Create desktop shortcut ───
$shortcutPath = Join-Path $HOME "Desktop\Moranville Pixel Office.lnk"
$launcherScript = Join-Path $pixelOffice "launch-casimir.ps1"

# Generate the launcher script (sets env vars then calls start.ps1)
$launcher = @"
# Auto-generated launcher for Moranville Pixel Office (Casimir side)
`$env:PIXEL_OFFICE_WHO = "casimir"
`$env:PIXEL_OFFICE_BRIDGE = "$bridge"
`$env:PIXEL_OFFICE_PORT = "$port"
& "$pixelOffice\start.ps1"
Write-Host ""
Write-Host "Pixel Office is live on http://localhost:$port"
Write-Host "Close this window to keep server running."
Write-Host "Press Enter to exit (server keeps running)..."
Read-Host
"@
Set-Content -Path $launcherScript -Value $launcher -Encoding UTF8

# Build .lnk
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments = "-NoExit -ExecutionPolicy Bypass -File `"$launcherScript`""
$Shortcut.IconLocation = "imageres.dll,76"  # Globe icon
$Shortcut.WorkingDirectory = $pixelOffice
$Shortcut.Description = "Moranville Pixel Office — Casimir side (sync via bridge)"
$Shortcut.Save()
Write-Host "✅ Desktop shortcut created: $shortcutPath" -ForegroundColor Green

# ─── Launch first time ───
Write-Host ""
Write-Host "→ Launching pixel-office for the first time..." -ForegroundColor Yellow
$env:PIXEL_OFFICE_WHO = "casimir"
$env:PIXEL_OFFICE_BRIDGE = $bridge
$env:PIXEL_OFFICE_PORT = $port
& "$pixelOffice\start.ps1"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "✅ Install done. Double-click 'Moranville Pixel Office' on your Desktop"
Write-Host "   any time you want to (re)start the dashboard."
Write-Host ""
Write-Host "   Dashboard URL:  http://localhost:$port"
Write-Host "   Bridge clone:   $bridge"
Write-Host "   Pixel-office:   $pixelOffice"
Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
