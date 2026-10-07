"""Loopback fake HTTP(S) server that imitates provider endpoints for tests."""

import json
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn


class _Server(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class FakeProviderServer(object):
    """Routes map (method, path) to a list of responses used in order.

    A response is a dict with ``status``, ``body`` (str, bytes, or JSON-able
    object), optional ``headers`` and ``delay`` seconds. The last response of
    a route repeats. ``on_request`` (if set) is called before replying.
    """

    def __init__(self, certfile=None, keyfile=None):
        self.routes = {}
        self.requests = []
        self.on_request = None
        self._lock = threading.Lock()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def _handle(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                path, _, query = self.path.partition("?")
                record = {
                    "method": self.command,
                    "path": path,
                    "query": query,
                    "headers": {k.lower(): v for k, v in self.headers.items()},
                    "body": body.decode("utf-8", "replace"),
                }
                with owner._lock:
                    owner.requests.append(record)
                    queue = owner.routes.get((self.command, path)) or [
                        {"status": 404, "body": {"error": {"message": "no route"}}}
                    ]
                    response = queue.pop(0) if len(queue) > 1 else queue[0]
                if owner.on_request:
                    owner.on_request(record)
                delay = response.get("delay", 0)
                if delay:
                    time.sleep(delay)
                payload = response.get("body", b"")
                if not isinstance(payload, (bytes, str)):
                    payload = json.dumps(payload)
                if isinstance(payload, str):
                    payload = payload.encode("utf-8")
                try:
                    self.send_response(response.get("status", 200))
                    headers = {"Content-Type": "application/json"}
                    headers.update(response.get("headers", {}))
                    for name, value in headers.items():
                        self.send_header(name, value)
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            do_GET = _handle
            do_POST = _handle

        self.httpd = _Server(("127.0.0.1", 0), Handler)
        self.scheme = "http"
        if certfile:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile, keyfile)
            self.httpd.socket = context.wrap_socket(
                self.httpd.socket, server_side=True
            )
            self.scheme = "https"
        self.port = self.httpd.server_address[1]
        self.base_url = "{}://127.0.0.1:{}".format(self.scheme, self.port)
        self.thread = threading.Thread(target=self.httpd.serve_forever)
        self.thread.daemon = True

    def route(self, method, path, *responses):
        with self._lock:
            self.routes[(method, path)] = list(responses)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()
        return False
