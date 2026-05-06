#!/usr/bin/env bash
# Start the pixel-office demo locally.
#   ./start.sh           → server on :8888
#   PIXEL_OFFICE_PORT=9000 ./start.sh
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PIXEL_OFFICE_ROOT="$ROOT"
mkdir -p "$ROOT/chats"
[ -f "$ROOT/events.json" ] || echo '{"events":[]}' > "$ROOT/events.json"

# Stop any running instance on the same port
PORT="${PIXEL_OFFICE_PORT:-8888}"
lsof -ti:"$PORT" 2>/dev/null | xargs -r kill 2>/dev/null || true
sleep 0.5

# Optional: start ack watcher in background
if [ "${ACK_WATCHER:-1}" = "1" ]; then
  pkill -f "$ROOT/ack-watcher.sh" 2>/dev/null || true
  bash "$ROOT/ack-watcher.sh" > "$ROOT/ack-watcher.log" 2>&1 &
  echo "[start] ack-watcher PID=$! (auto [seen] on incoming user-msg)"
fi

# Start server
python3 "$ROOT/server.py" > "$ROOT/server.log" 2>&1 &
SRV_PID=$!
sleep 1
echo "[start] server PID=$SRV_PID — http://localhost:$PORT"

# Open in default browser
if command -v open >/dev/null 2>&1; then open "http://localhost:$PORT"
elif command -v xdg-open >/dev/null 2>&1; then xdg-open "http://localhost:$PORT"
fi

echo "[start] tail logs: tail -f $ROOT/server.log"
echo "[start] stop:      kill $SRV_PID && pkill -f ack-watcher.sh"
