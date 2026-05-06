#!/usr/bin/env python3
"""
sync.py — bidirectional event sync via the Moranville-be/bridge GitHub repo.

Run this in the background alongside server.py. It does, every SYNC_INTERVAL seconds:
  1. Push: read events.json + my chats locally, append the *new* lines (filtered by ts)
     to bridge/pixel-events/<who>.jsonl, write bridge/pixel-events/<who>.heartbeat
     (current ISO timestamp), git commit + push.
  2. Pull: git pull, then read bridge/pixel-events/<other>.jsonl, merge any new
     events into events.json (deduplicated by event id).

The frontend's existing polling on /events.json + /chats/<agent>.json sees the
remote events automatically.

Env vars:
  PIXEL_OFFICE_WHO        = ferdi | casimir            (mandatory, "ferdi" if unset)
  PIXEL_OFFICE_OTHER      = casimir | ferdi            (auto-derived if unset)
  PIXEL_OFFICE_ROOT       = path to this script's dir  (auto)
  PIXEL_OFFICE_BRIDGE     = path to local clone of Moranville-be/bridge  (mandatory)
  PIXEL_OFFICE_SYNC_INTERVAL = seconds, default 8
"""
import json, os, sys, time, subprocess, shutil
from pathlib import Path

ROOT = Path(os.environ.get('PIXEL_OFFICE_ROOT', os.path.dirname(os.path.abspath(__file__))))
WHO = os.environ.get('PIXEL_OFFICE_WHO', 'ferdi').strip().lower()
OTHER = os.environ.get('PIXEL_OFFICE_OTHER', 'casimir' if WHO == 'ferdi' else 'ferdi').strip().lower()
BRIDGE = Path(os.environ.get('PIXEL_OFFICE_BRIDGE', '')).expanduser()
INTERVAL = int(os.environ.get('PIXEL_OFFICE_SYNC_INTERVAL', '8'))

EVENTS_FILE = ROOT / 'events.json'
PIXEL_EVENTS_DIR = BRIDGE / 'pixel-events'
MY_LOG = PIXEL_EVENTS_DIR / f'{WHO}.jsonl'
MY_HEARTBEAT = PIXEL_EVENTS_DIR / f'{WHO}.heartbeat'
OTHER_LOG = PIXEL_EVENTS_DIR / f'{OTHER}.jsonl'
OTHER_HEARTBEAT = PIXEL_EVENTS_DIR / f'{OTHER}.heartbeat'

LAST_PUSH_FILE = ROOT / '.sync-last-push.txt'
LAST_PULL_FILE = ROOT / '.sync-last-pull.txt'


def log(msg):
    print(f'[sync {WHO}] {time.strftime("%H:%M:%S")} {msg}', flush=True)


def now_iso():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def git(*args, check=True):
    """Run git in the bridge repo."""
    return subprocess.run(['git', '-C', str(BRIDGE), *args], capture_output=True, text=True, check=check)


def read_events_json():
    if not EVENTS_FILE.exists():
        return {'events': []}
    try:
        return json.load(open(EVENTS_FILE))
    except Exception:
        return {'events': []}


def write_events_json(data):
    tmp = EVENTS_FILE.with_suffix('.tmp')
    json.dump(data, open(tmp, 'w'))
    os.replace(tmp, EVENTS_FILE)


_last_heartbeat_push = 0
HEARTBEAT_INTERVAL = 60  # only push heartbeat at most once per N seconds


def push_step():
    """Append new local events to bridge, update heartbeat (throttled), git commit+push."""
    global _last_heartbeat_push
    PIXEL_EVENTS_DIR.mkdir(parents=True, exist_ok=True)

    # Load my events
    data = read_events_json()
    events = data.get('events', [])
    local_events = [e for e in events if e.get('source', WHO) == WHO]

    pushed_ids = set()
    if MY_LOG.exists():
        for line in MY_LOG.read_text().splitlines():
            try:
                ev = json.loads(line)
                pushed_ids.add(ev.get('id'))
            except Exception:
                pass

    new_events = [e for e in local_events if e.get('id') and e['id'] not in pushed_ids]
    has_new_events = len(new_events) > 0

    if has_new_events:
        with open(MY_LOG, 'a') as f:
            for ev in new_events:
                ev2 = dict(ev); ev2['source'] = WHO
                f.write(json.dumps(ev2) + '\n')

    # Heartbeat update is throttled — only every HEARTBEAT_INTERVAL seconds
    now = time.time()
    update_hb = (now - _last_heartbeat_push) >= HEARTBEAT_INTERVAL
    if has_new_events:
        update_hb = True  # also refresh hb if real events
    if update_hb:
        MY_HEARTBEAT.write_text(now_iso())
        _last_heartbeat_push = now

    # Skip git ops if nothing meaningful changed
    if not has_new_events and not update_hb:
        return

    # Git commit + push
    has_changes = git('status', '--porcelain', 'pixel-events', check=False).stdout.strip()
    if not has_changes:
        return
    git('add', 'pixel-events', check=False)
    if has_new_events:
        msg = f'sync({WHO}): +{len(new_events)} events, hb {now_iso()}'
    else:
        msg = f'sync({WHO}): heartbeat {now_iso()}'
    commit = git('commit', '-m', msg, check=False)
    if commit.returncode != 0:
        return
    push = git('push', 'origin', 'main', check=False)
    if push.returncode == 0:
        log(f'pushed: {msg}')
    else:
        log(f'push failed: {push.stderr.strip()[:100]}')


def pull_step():
    """Git pull, then merge other side events into local events.json."""
    fetch = git('fetch', 'origin', 'main', check=False)
    if fetch.returncode != 0:
        log(f'fetch failed: {fetch.stderr.strip()[:80]}')
        return
    # Rebase only if no local changes pending; else use ff merge
    pull = git('pull', '--rebase', '--autostash', 'origin', 'main', check=False)
    if pull.returncode != 0:
        log(f'pull failed: {pull.stderr.strip()[:80]}')
        return

    if not OTHER_LOG.exists():
        return

    # Read remote events (from "other")
    remote_events = []
    for line in OTHER_LOG.read_text().splitlines():
        try:
            remote_events.append(json.loads(line))
        except Exception:
            pass
    if not remote_events:
        return

    # Merge into local events.json
    local = read_events_json()
    local_events = local.get('events', [])
    seen_ids = {e.get('id') for e in local_events if e.get('id')}
    merged_count = 0
    for ev in remote_events:
        if ev.get('id') and ev['id'] not in seen_ids:
            ev2 = dict(ev)
            ev2.setdefault('source', OTHER)
            local_events.append(ev2)
            seen_ids.add(ev['id'])
            merged_count += 1
    if merged_count:
        local['events'] = local_events[-500:]
        write_events_json(local)
        log(f'merged {merged_count} remote events from {OTHER}')


def main():
    if not BRIDGE or not BRIDGE.exists():
        log(f'FATAL: bridge path not found: {BRIDGE}')
        log('Set PIXEL_OFFICE_BRIDGE to your local clone of Moranville-be/bridge.')
        sys.exit(1)

    log(f'sync starting — i am "{WHO}", peer is "{OTHER}"')
    log(f'bridge clone: {BRIDGE}')
    log(f'interval: {INTERVAL}s')

    while True:
        try:
            push_step()
            pull_step()
        except Exception as e:
            log(f'cycle error: {type(e).__name__}: {e}')
        time.sleep(INTERVAL)


if __name__ == '__main__':
    main()
