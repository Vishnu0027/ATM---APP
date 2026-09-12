"""
Dedicated Static File Server & Reverse Proxy for Touchscreen ATM Machine
Serves index.html, styles.css, and atm.js on port 8080 (separate from port 8000).
Transparently proxies /api requests to FastAPI backend on http://127.0.0.1:8000.
"""

import os
import sys
import mimetypes
import urllib.request
import urllib.error
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn

PORT = int(os.environ.get("ATM_PORT", 8080))
BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")
BASE_DIR = Path(__file__).resolve().parent

# Ensure common web MIME types
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/html", ".html")
mimetypes.add_type("application/json", ".json")
mimetypes.add_type("image/svg+xml", ".svg")


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class ATMServerHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def log_message(self, format, *args):
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")

    def end_headers(self):
        # Enable CORS and disable caching during development
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        # Proxy API calls directly to FastAPI backend
        if self.path.startswith("/api/"):
            self.proxy_to_backend()
            return

        clean_path = self.path.split("?")[0].split("#")[0]

        # Route root and /atm paths to index.html
        if clean_path in ["", "/", "/atm", "/atm/", "/index", "/index.html"]:
            self.serve_file("index.html", "text/html; charset=utf-8")
            return

        # Route /atm-static/<filename> to local folder
        if clean_path.startswith("/atm-static/"):
            rel_file = clean_path[len("/atm-static/"):]
            file_path = BASE_DIR / rel_file
            if file_path.is_file():
                content_type, _ = mimetypes.guess_type(str(file_path))
                self.serve_file(file_path.name, content_type or "application/octet-stream")
                return

        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            self.proxy_to_backend()
            return
        self.send_error(405, "Method Not Allowed")

    def proxy_to_backend(self):
        target_url = f"{BACKEND_URL.rstrip('/')}{self.path}"
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        req = urllib.request.Request(target_url, data=body, method=self.command)
        for header, value in self.headers.items():
            if header.lower() not in ["host", "content-length"]:
                req.add_header(header, value)

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.send_response(resp.status)
                for h, val in resp.headers.items():
                    if h.lower() not in ["transfer-encoding", "content-length", "access-control-allow-origin"]:
                        self.send_header(h, val)
                content = resp.read()
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            content = e.read()
            self.send_header("Content-Type", e.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_response(502)
            msg = f'{{"detail": "ATM backend proxy error: {str(e)}"}}'.encode("utf-8")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)

    def serve_file(self, filename, content_type):
        filepath = BASE_DIR / filename
        if not filepath.is_file():
            self.send_error(404, f"File not found: {filename}")
            return
        with open(filepath, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def main():
    server_address = ("127.0.0.1", PORT)
    try:
        httpd = ThreadedHTTPServer(server_address, ATMServerHandler)
    except OSError as e:
        print(f"[!] Could not bind to port {PORT}: {e}")
        sys.exit(1)

    print("=" * 60)
    print("  Starting Dedicated ATM Machine Terminal Server")
    print("=" * 60)
    print(f"ATM Terminal URL : http://127.0.0.1:{PORT}")
    print(f"ATM User Backend : {BACKEND_URL}")
    print(f"Files Served     : index.html, styles.css, atm.js")
    print("=" * 60)
    print(f"[*] Server running. Press Ctrl+C to stop.")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down ATM server...")
        httpd.server_close()


if __name__ == "__main__":
    main()
