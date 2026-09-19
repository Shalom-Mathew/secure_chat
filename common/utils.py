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
    ``recv`` (or one message splitting across two). ``send`` is thread-safe. ``recv`` must
    be called from a single reader thread; ``close`` may be called from any thread and
    wakes a blocked ``recv`` (which then returns None).
    """

    def __init__(self, sock: socket.socket):
        self.sock = sock
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # low latency for short chat lines
        self._buffer = bytearray()
        self._send_lock = threading.Lock()

    def send(self, obj: dict) -> None:
        data = (json.dumps(obj) + "\n").encode("utf-8")
        with self._send_lock:
            self.sock.sendall(data)

    def recv(self):
        """Return the next JSON object, or None when the connection was closed."""
        while True:
            newline = self._buffer.find(b"\n")
            if newline >= 0:
                line = bytes(self._buffer[:newline])
                del self._buffer[:newline + 1]
                return json.loads(line.decode("utf-8")) if line.strip() else self.recv()
            if len(self._buffer) > MAX_MESSAGE_BYTES:
                raise ValueError("message too large")
            try:
                chunk = self.sock.recv(65536)
            except OSError:
                return None
            if not chunk:
                return None
            self._buffer += chunk

    def close(self) -> None:
        for closer in (lambda: self.sock.shutdown(socket.SHUT_RDWR), self.sock.close):
            try:
                closer()
            except OSError:
                pass


def summarize_cipher(algorithm, encrypted) -> str:
    """Short, human-readable preview of a ciphertext (what an eavesdropper would see)."""
    if algorithm == "DES":
        return f"{str(encrypted)[:28]}…"
    try:
        first = encrypted[0]
        more = f" +{len(encrypted) - 1} more" if len(encrypted) > 1 else ""
        return f"[[{str(first[0])[:8]}…, {str(first[1])[:8]}…]]{more}"
    except (TypeError, IndexError, KeyError):
        return "…"
