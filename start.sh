#!/usr/bin/env bash
# Start the pixel-office demo locally with bridge-based sync.
#
#   ./start.sh                       # uses defaults: WHO=ferdi, PORT=8888
#   PIXEL_OFFICE_WHO=casimir ./start.sh
#   PIXEL_OFFICE_BRIDGE=~/code/bridge ./start.sh
#
# Required for sync: PIXEL_OFFICE_BRIDGE = path to local clone of
# https://github.com/Moranville-be/bridge

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PIXEL_OFFICE_ROOT="$ROOT"

# Defaults
export PIXEL_OFFICE_WHO="${PIXEL_OFFICE_WHO:-ferdi}"
export PIXEL_OFFICE_BRIDGE="${PIXEL_OFFICE_BRIDGE:-}"
PORT="${PIXEL_OFFICE_PORT:-8888}"
export PIXEL_OFFICE_PORT="$PORT"

mkdir -p "$ROOT/chats"
[ -f "$ROOT/events.json" ] || echo '{"events":[]}' > "$ROOT/events.json"

# Stop any running instance
lsof -ti:"$PORT" 2>/dev/null | xargs -r kill 2>/dev/null || true
pkill -f "$ROOT/sync.py" 2>/dev/null || true
pkill -f "$ROOT/ack-watcher.sh" 2>/dev/null || true
sleep 0.5

# Ack watcher
if [ "${ACK_WATCHER:-1}" = "1" ]; then
  bash "$ROOT/ack-watcher.sh" > "$ROOT/ack-watcher.log" 2>&1 &
  echo "[start] ack-watcher PID=$!"
fi

# Bridge sync (optional but recommended for cross-machine awareness)
if [ -n "$PIXEL_OFFICE_BRIDGE" ] && [ -d "$PIXEL_OFFICE_BRIDGE" ]; then
  python3 "$ROOT/sync.py" > "$ROOT/sync.log" 2>&1 &
  SYNC_PID=$!
  echo "[start] sync.py PID=$SYNC_PID  (who=$PIXEL_OFFICE_WHO, bridge=$PIXEL_OFFICE_BRIDGE)"
else
  echo "[start] sync DISABLED (set PIXEL_OFFICE_BRIDGE to enable)"
fi

# Server
python3 "$ROOT/server.py" > "$ROOT/server.log" 2>&1 &
SRV_PID=$!
sleep 1
echo "[start] server PID=$SRV_PID — http://localhost:$PORT  (who=$PIXEL_OFFICE_WHO)"

# Open browser
if command -v open >/dev/null 2>&1; then open "http://localhost:$PORT"
elif command -v xdg-open >/dev/null 2>&1; then xdg-open "http://localhost:$PORT"
fi

echo "[start] logs:  tail -f $ROOT/server.log $ROOT/sync.log $ROOT/ack-watcher.log"
echo "[start] stop:  kill $SRV_PID; pkill -f ack-watcher.sh; pkill -f sync.py"
