#!/usr/bin/env python3
"""
Tippspiel – lokaler Update-Server (Port 7373)
Läuft als launchd-Dienst (Mac) oder Windows-Autostart-Skript im Hintergrund.
Der Browser sendet POST /update → wm_auto.py wird ausgeführt.
GET /status → aktueller Fortschritt als JSON.
"""
import http.server
import json
import subprocess
import threading
import time
import sys
from pathlib import Path

PORT     = 7373
BASE_DIR = Path(__file__).parent.parent   # Projekt-Root

_status = {
    "running":     False,
    "log":         [],
    "last_update": None,
    "error":       None
}
_lock = threading.Lock()


def _run_update():
    """wm_auto.py im Hintergrund ausführen und Output zeilenweise mitschreiben."""
    with _lock:
        if _status["running"]:
            return
        _status.update({"running": True, "log": [], "error": None})

    script = BASE_DIR / "tools" / "wm_auto.py"
    try:
        proc = subprocess.Popen(
            [sys.executable, str(script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(BASE_DIR)
        )
        for line in proc.stdout:
            stripped = line.rstrip()
            if stripped:
                with _lock:
                    _status["log"].append(stripped)
        proc.wait()
        with _lock:
            _status["running"]     = False
            _status["last_update"] = time.strftime("%d.%m.%Y %H:%M")
            if proc.returncode != 0:
                _status["error"] = f"Fehler (exit {proc.returncode})"
    except Exception as e:
        with _lock:
            _status.update({"running": False, "error": str(e)})


class _Handler(http.server.BaseHTTPRequestHandler):
    def _send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/status":
            with _lock:
                data = dict(_status)
            self._send_json(data)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/update":
            threading.Thread(target=_run_update, daemon=True).start()
            self._send_json({"ok": True})
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass   # kein Output im Terminal/Log-File


if __name__ == "__main__":
    print(f"Tippspiel-Server läuft auf http://localhost:{PORT}  (Projekt: {BASE_DIR})",
          flush=True)
    server = http.server.HTTPServer(("127.0.0.1", PORT), _Handler)
    server.serve_forever()
