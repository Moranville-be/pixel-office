#!/usr/bin/env python3
"""
sync.py — bidirectional event sync via Moranville-be/bridge GitHub repo.

Push policy: only commits when there are NEW events to push (no heartbeat-only commits).
Author: "[bot] pixel-sync <bot@moranville.local>" so the Casimir watcher can filter.

Pull policy: every SYNC_INTERVAL seconds, fetch+pull --rebase, merge other side's
events.jsonl into the local events.json (deduped by id, marked source=<other>).

Presence is INFERRED by the dashboard from the timestamp of the most recent
event from each side. No heartbeat file.

Env vars:
  PIXEL_OFFICE_WHO            ferdi | casimir            (required)
  PIXEL_OFFICE_BRIDGE         path to local bridge clone (required)
  PIXEL_OFFICE_SYNC_INTERVAL  seconds, default 8
"""
import json, os, sys, time, subprocess
from pathlib import Path

ROOT = Path(os.environ.get('PIXEL_OFFICE_ROOT', os.path.dirname(os.path.abspath(__file__))))
WHO = os.environ.get('PIXEL_OFFICE_WHO', 'ferdi').strip().lower()
OTHER = 'casimir' if WHO == 'ferdi' else 'ferdi'
BRIDGE = Path(os.environ.get('PIXEL_OFFICE_BRIDGE', '')).expanduser()
INTERVAL = int(os.environ.get('PIXEL_OFFICE_SYNC_INTERVAL', '8'))

EVENTS_FILE = ROOT / 'events.json'
PIXEL_EVENTS_DIR = BRIDGE / 'pixel-events'
MY_LOG = PIXEL_EVENTS_DIR / f'{WHO}.jsonl'
OTHER_LOG = PIXEL_EVENTS_DIR / f'{OTHER}.jsonl'

# Bot identity for commits — Casimir's watcher should filter on this author
BOT_NAME = '[bot] pixel-sync'
BOT_EMAIL = 'bot@moranville.local'

# Optional cap on local events file growth
MAX_LOCAL_EVENTS = 500


def log(msg):
    print(f'[sync {WHO}] {time.strftime("%H:%M:%S")} {msg}', flush=True)


def now_iso():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def git(*args, check=False):
    return subprocess.run(['git', '-C', str(BRIDGE), *args],
                          capture_output=True, text=True, check=check)


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


def push_step():
    """Append local events that haven't been pushed yet, commit + push only if new."""
    PIXEL_EVENTS_DIR.mkdir(parents=True, exist_ok=True)

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
    if not new_events:
        return  # NOTHING to push, no commit

    with open(MY_LOG, 'a') as f:
        for ev in new_events:
            ev2 = dict(ev); ev2['source'] = WHO
            f.write(json.dumps(ev2) + '\n')

    has_changes = git('status', '--porcelain', 'pixel-events').stdout.strip()
    if not has_changes:
        return
    git('add', 'pixel-events')
    msg = f'pixel-sync({WHO}): +{len(new_events)} events'
    commit = git('-c', f'user.name={BOT_NAME}', '-c', f'user.email={BOT_EMAIL}',
                 'commit', '-m', msg)
    if commit.returncode != 0:
        log(f'commit failed: {commit.stderr.strip()[:120]}')
        return
    push = git('push', 'origin', 'main')
    if push.returncode == 0:
        log(f'pushed: {msg}')
    else:
        log(f'push failed: {push.stderr.strip()[:120]}')


def pull_step():
    """Git pull, then merge other side events into local events.json."""
    fetch = git('fetch', 'origin', 'main')
    if fetch.returncode != 0:
        return
    pull = git('pull', '--rebase', '--autostash', 'origin', 'main')
    if pull.returncode != 0:
        log(f'pull failed: {pull.stderr.strip()[:80]}')
        return
    if not OTHER_LOG.exists():
        return

    remote_events = []
    for line in OTHER_LOG.read_text().splitlines():
        try:
            remote_events.append(json.loads(line))
        except Exception:
            pass
    if not remote_events:
        return

    local = read_events_json()
    local_events = local.get('events', [])
    seen_ids = {e.get('id') for e in local_events if e.get('id')}
    merged = 0
    for ev in remote_events:
        if ev.get('id') and ev['id'] not in seen_ids:
            ev2 = dict(ev)
            ev2.setdefault('source', OTHER)
            local_events.append(ev2)
            seen_ids.add(ev['id'])
            merged += 1
    if merged:
        local['events'] = local_events[-MAX_LOCAL_EVENTS:]
        write_events_json(local)
        log(f'merged {merged} remote events from {OTHER}')


def main():
    if not BRIDGE or not BRIDGE.exists():
        log(f'FATAL: bridge path not found: {BRIDGE}')
        sys.exit(1)

    log(f'sync starting — i am "{WHO}", peer is "{OTHER}"')
    log(f'bridge clone: {BRIDGE}')
    log(f'interval: {INTERVAL}s — push only when new events, no heartbeat')
    log(f'commit author: {BOT_NAME} <{BOT_EMAIL}>')

    while True:
        try:
            push_step()
            pull_step()
        except Exception as e:
            log(f'cycle error: {type(e).__name__}: {e}')
        time.sleep(INTERVAL)


if __name__ == '__main__':
    main()
