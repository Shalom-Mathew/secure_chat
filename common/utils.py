"""Shared constants and the newline-delimited JSON transport used by client and server."""

import json
import os
import socket
import threading

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5000
MAX_MESSAGE_BYTES = 16 * 1024 * 1024  # one JSON line; guards against unbounded reads
DEFAULT_DES_KEY = b"secret12"  # demo pre-shared key; override with SECURE_CHAT_DES_KEY


def get_des_key() -> bytes:
    """Return the pre-shared DES key (env var SECURE_CHAT_DES_KEY, else the demo default)."""
    return os.environ.get("SECURE_CHAT_DES_KEY", "").encode("utf-8") or DEFAULT_DES_KEY


class JsonChannel:
    """Send and receive one JSON object per line over a connected socket.

    Line framing fixes the classic TCP problem of two messages merging into one
    ``recv`` (or one message splitting across two). ``send`` is thread-safe.
    """

    def __init__(self, sock: socket.socket):
        self.sock = sock
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # low latency for short chat lines
        self._reader = sock.makefile("rb")
        self._send_lock = threading.Lock()

    def send(self, obj: dict) -> None:
        data = (json.dumps(obj) + "\n").encode("utf-8")
        with self._send_lock:
            self.sock.sendall(data)

    def recv(self):
        """Return the next JSON object, or None when the peer closed the connection."""
        line = self._reader.readline(MAX_MESSAGE_BYTES + 1)
        if not line:
            return None
        if len(line) > MAX_MESSAGE_BYTES:
            raise ValueError("message too large")
        return json.loads(line.decode("utf-8"))

    def close(self) -> None:
        for closer in (lambda: self.sock.shutdown(socket.SHUT_RDWR), self._reader.close, self.sock.close):
            try:
                closer()
            except OSError:
                pass
