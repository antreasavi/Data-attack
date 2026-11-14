"""Local web server (127.0.0.1 only): the page, a JSON state endpoint and a live event stream."""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

STATIC = os.path.join(os.path.dirname(__file__), 'static')
TYPES = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
         '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml', '.ico': 'image/x-icon'}


def make_handler(engine):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype='application/json'):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == '/api/state':
                return self._send(200, engine.snapshot()[0])
            if path == '/api/stream':
                return self._stream()
            name = 'index.html' if path in ('/', '') else path.lstrip('/')
            full = os.path.normpath(os.path.join(STATIC, name))
            if not full.startswith(STATIC) or not os.path.isfile(full):
                return self._send(404, {'error': 'not found'})
            with open(full, 'rb') as f:
                self._send(200, f.read(), TYPES.get(os.path.splitext(full)[1], 'application/octet-stream'))

        def do_POST(self):
            path = urlparse(self.path).path
            try:
                body = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'{}')
                if path == '/api/scenario':
                    engine.set_scenario(mode=body.get('mode'), fade=body.get('fade'),
                                        set_edits=body.get('set'), reset=bool(body.get('reset')))
                elif path == '/api/speaker':
                    engine.speaker_action(body)
                else:
                    return self._send(404, {'error': 'not found'})
                return self._send(200, engine.snapshot()[0])
            except Exception as exc:
                return self._send(400, {'error': f'{type(exc).__name__}: {exc}'})

        def _stream(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            seen = -1
            try:
                while True:
                    with engine.changed:
                        if engine.version == seen:
                            engine.changed.wait(timeout=15)
                        state, ver = engine.state, engine.version
                    if ver != seen:
                        self.wfile.write(b'data: ' + json.dumps(state).encode() + b'\n\n')
                        seen = ver
                    else:
                        self.wfile.write(b': keep-alive\n\n')
                    self.wfile.flush()
            except (ConnectionError, OSError):
                return

    return Handler


def serve(engine, host='127.0.0.1', port=8791):
    httpd = ThreadingHTTPServer((host, port), make_handler(engine))
    httpd.daemon_threads = True
    t = threading.Thread(target=httpd.serve_forever, name='http', daemon=True)
    t.start()
    return httpd
