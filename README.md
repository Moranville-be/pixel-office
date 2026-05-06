# Pixel Office — Moranville Bridge

Live dashboard for the Moranville inter-Claude orchestration:
visualize Ferdi (server orchestrator) and Kasi (asset-manager orchestrator)
along with their sub-agents in a top-down pixel-art office.

![demo](docs/demo.gif)

## What it shows

- **2 orchestrators** — `Ferdi` (Claude 1, server-side) and `Kasi` (Claude 2, AM-side) sat at their desks, typing.
- **2 teams of 10 small desks** — sub-agents spawn and walk to a free desk, work for a while, then leave.
- **Live activity log** — every spawn / message / completion in the sidebar.
- **Click any sprite → terminal drawer** — talk to the agent (real chat, file-backed). For orchestrators, you're talking to the actual Claude session driving them.
- **Sub-agents only spawn from an orchestrator** — strict hierarchy, never standalone.

## Prerequisites

- Python 3.8+ (no extra dependencies — uses stdlib only)
- A modern browser (Chrome/Firefox/Safari)
- macOS or Linux: bash. Windows: PowerShell 5.1+.

## Quick start

### macOS / Linux

```bash
git clone https://github.com/Moranville-be/pixel-office.git
cd pixel-office
./start.sh           # opens http://localhost:8888 in your default browser
```

### Windows (PowerShell)

```powershell
git clone https://github.com/Moranville-be/pixel-office.git
cd pixel-office
.\start.ps1          # opens http://localhost:8888
```

Custom port: `PIXEL_OFFICE_PORT=9000 ./start.sh` (or `$env:PIXEL_OFFICE_PORT=9000` on Windows).

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│ Browser (dashboard)                                              │
│  ┌─────────────────────┐       ┌──────────────────────────┐      │
│  │ Pixel office stage  │       │ Sidebar / activity log   │      │
│  │ (sprites animated)  │       │ (orchestrators + subs)   │      │
│  └─────────────────────┘       └──────────────────────────┘      │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ Drawer terminal (click on a sprite to open)             │     │
│  │   - shows the agent's stdout/messages                    │     │
│  │   - input field → POST /chat                             │     │
│  └─────────────────────────────────────────────────────────┘     │
└─────────────┬─────────────────────────────────────┬─────────────┘
              │ GET events.json (poll 1.5s)          │ POST /chat
              │ GET chats/<id>.json                  │
              ▼                                       ▼
┌──────────────────────────────────────────────────────────────────┐
│ server.py (stdlib http.server)                                   │
│  - serves index.html, sprites/*, events.json, chats/<id>.json    │
│  - POST /chat → appends to chats/<agent>.jsonl + events.json     │
└────────────────┬─────────────────────────────────────────────────┘
                 │
                 ▼
        events.json (event queue)
        chats/<agent>.jsonl (chat history per agent)
                 ▲
                 │ append events from outside (Claude session)
                 │
        ┌────────┴────────┐
        │ event.py CLI    │
        │  spawn / log /  │
        │  msg / done     │
        └─────────────────┘
```

## Wiring it to a real Claude session

The `event.py` helper is what your **orchestrator Claude** (Ferdi or Kasi) uses to:

1. **Spawn a sub-agent** when it dispatches a task:
   ```bash
   ./event.py spawn claude-1 "Audit Payload sync API" Atlas
   # prints agentEventId, e.g.: 2d684abd
   ```

2. **Stream stdout** from the sub-agent:
   ```bash
   ./event.py log 2d684abd '$ curl -sI https://dev.moranville.be/api/sync/artworks'
   ```

3. **Send a message from the agent** (rendered green in the drawer):
   ```bash
   ./event.py msg 2d684abd 'HTTP/2 200 OK · 63 artworks fetched'
   ```

4. **Close** the sub-agent when done:
   ```bash
   ./event.py done 2d684abd 'Audit complete · 0 issues'
   ```

For replying to a user message in the drawer (chat with the orchestrator):
```bash
./event.py msg claude-1 'Hello, here is my answer…'   # appears in Ferdi drawer
./event.py msg claude-2 'Voici ce que je vois côté AM…' # appears in Kasi drawer
```

## Background ack watcher (macOS/Linux)

`ack-watcher.sh` runs in the background and posts a **`[seen]`** message in the
agent's terminal as soon as a new user message arrives — so users get instant
feedback while waiting for the real orchestrator reply.

It starts automatically with `start.sh`. To disable: `ACK_WATCHER=0 ./start.sh`.

## Sprites

Character / furniture sprites are licensed under MIT, sourced from
[`pablodelucca/pixel-agents`](https://github.com/pablodelucca/pixel-agents)
(itself derived from JIK-A-4's [Metro City pack](https://jik-a-4.itch.io/metrocity-free-topdown-character-pack)).

## Cross-machine sync (via bridge GitHub) — ✅ shipped

Set `PIXEL_OFFICE_BRIDGE` to a local clone of
[Moranville-be/bridge](https://github.com/Moranville-be/bridge) and `start.sh`
will launch `sync.py` in the background:

```bash
git clone https://github.com/Moranville-be/bridge.git ~/.moranville-bridge
PIXEL_OFFICE_WHO=ferdi PIXEL_OFFICE_BRIDGE=~/.moranville-bridge ./start.sh
```

What it does, every 8 seconds:

1. **Push** new local events to `bridge/pixel-events/<who>.jsonl` (append-only),
   refresh `bridge/pixel-events/<who>.heartbeat` (throttled to 1/min), commit + push.
2. **Pull** `git pull --rebase`, merge `bridge/pixel-events/<other>.jsonl` into
   local `events.json` (deduplicated by event id, marked with `source: <other>`).

The frontend's `/api/state.json` exposes orchestrator presence based on
heartbeat freshness:

- `working` — heartbeat <120s ago + recent event <60s ago
- `online-idle` — heartbeat <120s ago, no recent event
- `offline` — heartbeat absent or >120s old

Both sides see the same office, both sets of sub-agents.

## Desktop shortcut (macOS)

A `.command` file you can place on your Desktop:

```bash
#!/usr/bin/env bash
PIXEL_OFFICE="$HOME/.moranville-pixel-office"
BRIDGE="$HOME/.moranville-bridge"
[ -d "$PIXEL_OFFICE" ] || git clone https://github.com/Moranville-be/pixel-office.git "$PIXEL_OFFICE"
[ -d "$BRIDGE" ]       || git clone https://github.com/Moranville-be/bridge.git "$BRIDGE"
( cd "$PIXEL_OFFICE" && git pull --rebase --autostash )
( cd "$BRIDGE" && git pull --rebase --autostash )
PIXEL_OFFICE_WHO=ferdi PIXEL_OFFICE_BRIDGE="$BRIDGE" bash "$PIXEL_OFFICE/start.sh"
```

Save as `~/Desktop/Moranville Pixel Office.command`, `chmod +x` it, then
double-click. First run clones the repos automatically; subsequent runs pull
the latest and start the server.

For **Casimir on Windows**, the equivalent `.lnk` shortcut points to a wrapper
that runs `start.ps1` with `$env:PIXEL_OFFICE_WHO = "casimir"`.

## Roadmap

- [x] Cross-machine sync via Moranville-be/bridge
- [ ] **Real-time chat → orchestrator** via Server-Sent Events (replace polling)
- [ ] **Search** in the terminal drawer (Cmd/Ctrl+F)
- [ ] **Persistent state** between server restarts
- [ ] **Custom layout editor** — drag desks around, save layouts as JSON
- [ ] **Office themes** — dark / Game Boy / Stardew / etc.

## Inspiration & credits

- [pablodelucca/pixel-agents](https://github.com/pablodelucca/pixel-agents) — the original VS Code extension that inspired this dashboard
- [JIK-A-4 Metro City pack](https://jik-a-4.itch.io/metrocity-free-topdown-character-pack) — character sprites
- Convex's [AI Town](https://github.com/a16z-infra/ai-town) — for the spatial-agent paradigm

## License

MIT — see [LICENSE](LICENSE).
