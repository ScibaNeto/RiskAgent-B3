import json
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .live_market import LiveMarket


def serve(page, archive, port, open_browser):
    market = LiveMarket(archive)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                content, mime = page.read_bytes(), "text/html; charset=utf-8"
            elif self.path == "/api/petr4":
                content = json.dumps(market.snapshot()).encode()
                mime = "application/json"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        url = f"http://127.0.0.1:{server.server_port}/"
        print(url, flush=True)
        if open_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
