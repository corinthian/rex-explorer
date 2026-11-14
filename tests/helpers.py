"""Shared test helpers: stubbed Last.fm client and an in-process server.
Nothing here touches the network."""

import http.client
import socket
import sys
import threading
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import server  # noqa: E402
from lastfm import LastFM  # noqa: E402


def make_client(cache_dir, responder):
    """LastFM whose HTTP layer is `responder(params) -> payload dict`.
    client.calls lists the params of every stubbed network call."""
    client = LastFM("dummy", cache_dir=Path(cache_dir))
    client._min_interval = 0
    client.calls = []
    lock = threading.Lock()

    def fake_get(url, params=None, **kwargs):
        with lock:
            client.calls.append(dict(params))
        resp = Mock()
        resp.status_code = 200
        resp.json.return_value = responder(params)
        return resp

    client._session.get = fake_get
    return client


def _no_network(*args, **kwargs):
    raise AssertionError("test tried to reach the network")


@contextmanager
def running_server(client=None, fetch_image=None):
    """Serve server.Handler on an ephemeral loopback port; yields the port."""
    get_client = (lambda: client) if client is not None else _no_network
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    with patch.object(server, "get_client", get_client), \
            patch.object(server, "_fetch_image_url", fetch_image or _no_network):
        thread.start()
        try:
            yield httpd.server_address[1]
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(5)


def request(port, method, path, headers=None):
    """Returns (status, lowercased header dict, body bytes)."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request(method, path, headers=headers or {})
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, body
    finally:
        conn.close()


def raw_request(port, method, path):
    """Send one request on a bare socket; returns (head text, body bytes)
    exactly as they came off the wire."""
    with socket.create_connection(("127.0.0.1", port), timeout=10) as sock:
        sock.sendall(f"{method} {path} HTTP/1.1\r\nHost: test\r\n"
                     f"Connection: close\r\n\r\n".encode())
        chunks = []
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
    head, _, body = b"".join(chunks).partition(b"\r\n\r\n")
    return head.decode("iso-8859-1"), body
