#!/usr/bin/env python3
"""
Custom HTTP server for the pixel-office demo.
- GET  /                   → serves index.html and static files
- GET  /events.json        → events queue (consumed by dashboard polling)
- GET  /chats/<id>.json    → chat history for an agent (consumed by dashboard)
- POST /chat               → body {agent, message} appends to chats/<agent>.jsonl
                              + appends an event "user-msg" to events.json
"""
import http.server, socketserver, json, os, time, uuid, urllib.parse

ROOT = os.environ.get('PIXEL_OFFICE_ROOT', os.path.dirname(os.path.abspath(__file__)))
CHATS = os.path.join(ROOT, 'chats')
EVENTS = os.path.join(ROOT, 'events.json')
PORT = int(os.environ.get('PIXEL_OFFICE_PORT', 8888))
WHO = os.environ.get('PIXEL_OFFICE_WHO', 'ferdi').strip().lower()
BRIDGE = os.environ.get('PIXEL_OFFICE_BRIDGE', '')

# WebSocket hub (Jarvis-hosted, shared between Ferdi + Casimir)
WS_URL = os.environ.get('PIXEL_OFFICE_WS_URL', 'wss://pixel.ferdi.wtf/ws')
WS_TOKEN = os.environ.get('PIXEL_OFFICE_WS_TOKEN', '')


def parse_iso_utc(ts):
    """Parse 'YYYY-MM-DDTHH:MM:SSZ' as UTC seconds since epoch."""
    import calendar
    return calendar.timegm(time.strptime(ts, '%Y-%m-%dT%H:%M:%SZ'))


def last_event_age(who):
    """Returns age in seconds of the most recent event from <who>, or +inf if none."""
    try:
        data = json.load(open(EVENTS))
        events = [e for e in data.get('events', []) if e.get('source', WHO) == who]
        if not events:
            return float('inf')
        last = events[-1].get('ts', '')
        if not last:
            return float('inf')
        return time.time() - parse_iso_utc(last)
    except Exception:
        return float('inf')


def status_for(who):
    """Presence inferred from event recency.
       Self (WHO == who): always at least 'online-idle' since server is up.
       Other side: 'offline' if no recent event seen via sync.
    """
    age = last_event_age(who)
    if who == WHO:
        # I'm here as long as the server runs
        if age < 60:
            return 'working'
        return 'online-idle'
    # Other side
    if age == float('inf'):
        return 'offline'
    if age < 60:
        return 'working'
    if age < 1800:  # 30 min
        return 'online-idle'
    return 'offline'

os.makedirs(CHATS, exist_ok=True)
if not os.path.exists(EVENTS):
    json.dump({'events': []}, open(EVENTS, 'w'))


def append_event(ev):
    data = json.load(open(EVENTS))
    data.setdefault('events', []).append(ev)
    data['events'] = data['events'][-200:]
    json.dump(data, open(EVENTS, 'w'))


def append_chat(agent_id, line):
    path = os.path.join(CHATS, f'{agent_id}.jsonl')
    with open(path, 'a') as f:
        f.write(json.dumps(line) + '\n')


def read_chat(agent_id):
    path = os.path.join(CHATS, f'{agent_id}.jsonl')
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as f:
        for raw in f:
            raw = raw.strip()
            if not raw: continue
            try: out.append(json.loads(raw))
            except: pass
    return out


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def do_GET(self):
        # /chats/<agent_id>.json — chat history
        if self.path.startswith('/chats/') and self.path.endswith('.json'):
            agent_id = self.path[len('/chats/'):-len('.json')]
            agent_id = urllib.parse.unquote(agent_id).split('?')[0]
            payload = json.dumps({'agent': agent_id, 'lines': read_chat(agent_id)})
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(payload.encode('utf-8'))
            return
        # /api/config.json — frontend bootstrap (WS endpoint, identity, token)
        if self.path.startswith('/api/config.json'):
            payload = json.dumps({
                'who': WHO,
                'ws_url': WS_URL,
                'ws_token': WS_TOKEN,  # exposed to localhost frontend only
            })
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(payload.encode('utf-8'))
            return
        # /api/state.json — orchestrator presence (event-based, no heartbeat file)
        if self.path.startswith('/api/state.json'):
            payload = json.dumps({
                'me': WHO,
                'agents': {
                    'ferdi':   {'status': status_for('ferdi'),
                                'last_event_age_seconds': round(last_event_age('ferdi'), 1) if last_event_age('ferdi') != float('inf') else None},
                    'casimir': {'status': status_for('casimir'),
                                'last_event_age_seconds': round(last_event_age('casimir'), 1) if last_event_age('casimir') != float('inf') else None},
                },
                'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            })
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(payload.encode('utf-8'))
            return
        # default static serving
        super().do_GET()

    def do_POST(self):
        if self.path != '/chat':
            self.send_error(404, 'Only POST /chat is supported')
            return
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8') if length else ''
        try:
            data = json.loads(body)
        except Exception:
            self.send_error(400, 'Invalid JSON')
            return
        agent = data.get('agent')
        message = data.get('message')
        if not agent or not message:
            self.send_error(400, 'Missing agent or message')
            return
        ts = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        line = {
            'id': str(uuid.uuid4()),
            'ts': ts,
            'agent': agent,
            'role': 'user',
            'message': message,
        }
        append_chat(agent, line)
        # Also append a "user-msg" event so the drawer can render in real time
        ev = {
            'id': str(uuid.uuid4()),
            'ts': ts,
            'type': 'user-msg',
            'agentEventId': agent,  # use agent id directly as the routing key
            'line': message,
            'source': WHO,
            'sandbox_scope': 'moranville-bridge',  # policy hint for the receiving Claude
        }
        append_event(ev)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'ok': True, 'id': line['id']}).encode('utf-8'))

    def log_message(self, fmt, *args):
        # Silence default access log
        return


class ReusableTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


if __name__ == '__main__':
    with ReusableTCPServer(('127.0.0.1', PORT), Handler) as httpd:
        print(f'Pixel office demo serving on http://localhost:{PORT}')
        httpd.serve_forever()
