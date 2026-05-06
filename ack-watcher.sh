#!/usr/bin/env bash
# ack-watcher.sh — auto-acknowledges incoming user messages on chats/<agent>.jsonl
# so the dashboard shows "[seen]" instantly. The real reply still comes from the
# orchestrator Claude when it next reads the chat.
set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"
SEEN_DIR="$ROOT/.ack-seen"
mkdir -p "$SEEN_DIR"

while true; do
  for chat in "$ROOT"/chats/*.jsonl; do
    [ -f "$chat" ] || continue
    agent="$(basename "$chat" .jsonl)"
    seen_file="$SEEN_DIR/$agent.last_id"
    last_seen="$(cat "$seen_file" 2>/dev/null || echo '')"
    # Find the last line id
    last_line="$(tail -n 1 "$chat" 2>/dev/null)"
    [ -z "$last_line" ] && continue
    last_id="$(echo "$last_line" | python3 -c 'import json,sys
try:
  d=json.loads(sys.stdin.read())
  print(d.get("id",""))
except: print("")' 2>/dev/null)"
    [ -z "$last_id" ] && continue
    if [ "$last_id" != "$last_seen" ]; then
      role="$(echo "$last_line" | python3 -c 'import json,sys
try:
  d=json.loads(sys.stdin.read())
  print(d.get("role",""))
except: print("")' 2>/dev/null)"
      if [ "$role" = "user" ]; then
        # Auto-ack [seen]
        "$ROOT/event.py" msg "$agent" "[seen — orchestrator will reply when prompted]" >/dev/null 2>&1
      fi
      echo "$last_id" > "$seen_file"
    fi
  done
  sleep 1
done
