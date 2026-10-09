from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


FIXTURES = Path("/fixtures")
GRID = (FIXTURES / "grid_real_2026-09-21.html").read_bytes()
WEATHER = (FIXTURES / "webpilot_weather_pecem.html").read_bytes()
LOGIN = b'<html><input id="tbSenha"></html>'


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/maneuvers":
            body = GRID
        elif self.path == "/weather":
            body = WEATHER
        elif self.path == "/login":
            body = LOGIN
        elif self.path == "/healthz":
            body = b"ok"
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


server = ThreadingHTTPServer(("0.0.0.0", 8081), Handler)
print("fake webpilot synthetic fixture server: READY")
server.serve_forever()
