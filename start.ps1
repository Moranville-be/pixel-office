# start.ps1 — Windows launcher for pixel-office
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
$env:PIXEL_OFFICE_ROOT = $root
$port = if ($env:PIXEL_OFFICE_PORT) { $env:PIXEL_OFFICE_PORT } else { "8888" }

New-Item -ItemType Directory -Path "$root\chats" -Force | Out-Null
if (-not (Test-Path "$root\events.json")) {
  '{"events":[]}' | Out-File "$root\events.json" -Encoding utf8
}

# Kill any process on the port
$existing = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
if ($existing) {
  $existing.OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
  Start-Sleep 1
}

# Optional ack-watcher (PowerShell version is tricky; skip on Windows for now,
# users can rely on the pure orchestrator-reply flow)

# Start server in a hidden process
$server = Start-Process -FilePath "python" -ArgumentList "$root\server.py" -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput "$root\server.log" -RedirectStandardError "$root\server.err.log"
Start-Sleep 1
Write-Host "[start] server PID=$($server.Id) — http://localhost:$port"

# Open browser
Start-Process "http://localhost:$port"

Write-Host "[start] stop: Stop-Process -Id $($server.Id)"
