# start.ps1 — Windows launcher for pixel-office
# Set PIXEL_OFFICE_WHO=casimir + PIXEL_OFFICE_BRIDGE=<path-to-bridge-clone> for sync
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
$env:PIXEL_OFFICE_ROOT = $root
if (-not $env:PIXEL_OFFICE_WHO)    { $env:PIXEL_OFFICE_WHO = "casimir" }
$port = if ($env:PIXEL_OFFICE_PORT) { $env:PIXEL_OFFICE_PORT } else { "8888" }
$env:PIXEL_OFFICE_PORT = $port

New-Item -ItemType Directory -Path "$root\chats" -Force | Out-Null
if (-not (Test-Path "$root\events.json")) {
  '{"events":[]}' | Out-File "$root\events.json" -Encoding utf8
}

# Kill any process on the port + previous sync
$existing = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
if ($existing) {
  $existing.OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
  Start-Sleep 1
}
Get-Process python -ErrorAction SilentlyContinue | Where-Object {
  $_.MainWindowTitle -match 'sync.py|server.py' -or $_.ProcessName -eq 'python'
} | Out-Null  # naive cleanup

# Bridge sync (optional, recommended)
if ($env:PIXEL_OFFICE_BRIDGE -and (Test-Path $env:PIXEL_OFFICE_BRIDGE)) {
  $sync = Start-Process -FilePath "python" -ArgumentList "$root\sync.py" -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput "$root\sync.log" -RedirectStandardError "$root\sync.err.log"
  Write-Host "[start] sync.py PID=$($sync.Id)  who=$($env:PIXEL_OFFICE_WHO), bridge=$($env:PIXEL_OFFICE_BRIDGE)"
} else {
  Write-Host "[start] sync DISABLED (set `$env:PIXEL_OFFICE_BRIDGE to enable)"
}

# Start server
$server = Start-Process -FilePath "python" -ArgumentList "$root\server.py" -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput "$root\server.log" -RedirectStandardError "$root\server.err.log"
Start-Sleep 1
Write-Host "[start] server PID=$($server.Id) — http://localhost:$port  who=$($env:PIXEL_OFFICE_WHO)"

# Open browser
Start-Process "http://localhost:$port"
Write-Host "[start] stop: Stop-Process -Id $($server.Id)"
