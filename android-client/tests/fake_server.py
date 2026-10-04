"""Loopback-only test server; never imports the real PC keyboard/paste code."""
import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

events = []
mode = "ok"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, body):
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_HEAD(self):
        self.send_response(200 if self.path == "/last_text" else 404)
        self.end_headers()

    def do_GET(self):
        self.reply({"events": events})

    def do_POST(self):
        global mode
        data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/mode":
            mode = data["mode"]
            events.clear()
            self.reply({"success": True})
            return
        events.append({"path": self.path, "data": data})
        if mode == "delayed_type" and self.path == "/type":
            time.sleep(0.4)
        failed = (mode == "preview_error" and self.path == "/input_preview") or (
            mode == "type_error" and self.path == "/type"
        )
        self.reply({"success": not failed})


HTTPServer(("127.0.0.1", 15001), Handler).serve_forever()
