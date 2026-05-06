#!/usr/bin/env python3
"""Helper: append events to events.json (file-based queue for the dashboard).

Override the data root with PIXEL_OFFICE_ROOT env var (default = same dir as this script).
"""
import json, sys, time, uuid, os

ROOT = os.environ.get('PIXEL_OFFICE_ROOT', os.path.dirname(os.path.abspath(__file__)))
EVENTS = os.path.join(ROOT, 'events.json')

def append(ev):
    if os.path.exists(EVENTS):
        try: data = json.load(open(EVENTS))
        except: data = {'events': []}
    else:
        data = {'events': []}
    if 'events' not in data: data['events'] = []
    data['events'].append(ev)
    data['events'] = data['events'][-200:]
    json.dump(data, open(EVENTS, 'w'))

def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

def main():
    if len(sys.argv) < 2:
        print("usage:")
        print("  event.py spawn <parent> <role>            → returns agentEventId")
        print("  event.py log <agentEventId> <line>")
        print("  event.py done <agentEventId> [summary]")
        print("  event.py msg <agentEventId> <line>        (agent says something to user)")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == 'spawn':
        parent, role = sys.argv[2], sys.argv[3]
        name = sys.argv[4] if len(sys.argv) > 4 else None
        aid = str(uuid.uuid4())[:8]
        ev = {'id': str(uuid.uuid4()), 'ts': now(), 'type': 'spawn',
              'parent': parent, 'role': role, 'agentEventId': aid}
        if name: ev['name'] = name
        append(ev)
        print(aid)
    elif cmd == 'log':
        aid, line = sys.argv[2], ' '.join(sys.argv[3:])
        append({'id': str(uuid.uuid4()), 'ts': now(), 'type': 'log',
                'agentEventId': aid, 'line': line})
        print('OK')
    elif cmd == 'msg':
        aid, line = sys.argv[2], ' '.join(sys.argv[3:])
        append({'id': str(uuid.uuid4()), 'ts': now(), 'type': 'msg',
                'agentEventId': aid, 'line': line})
        print('OK')
    elif cmd == 'done':
        aid = sys.argv[2]
        summary = ' '.join(sys.argv[3:]) if len(sys.argv) > 3 else 'completed'
        append({'id': str(uuid.uuid4()), 'ts': now(), 'type': 'done',
                'agentEventId': aid, 'summary': summary})
        print('OK')
    else:
        print("unknown cmd", cmd); sys.exit(1)

if __name__ == '__main__':
    main()
