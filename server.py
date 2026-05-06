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
        append_event({
            'id': str(uuid.uuid4()),
            'ts': ts,
            'type': 'user-msg',
            'agentEventId': agent,  # use agent id directly as the routing key
            'line': message,
        })
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
