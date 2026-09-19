"""Chat relay server.

Clients register a name (plus an ElGamal public key); the server keeps a directory of
connected peers, announces joins/leaves, and relays encrypted messages between them.
Run with:  python -m server.server [--host H] [--port P] [--hide-plaintext]
"""

import argparse
import socket
import sys
import threading

from common.utils import DEFAULT_HOST, DEFAULT_PORT, JsonChannel, summarize_cipher
from crypto.elgamal_crypto import validate_public_key


def _safe_print(*args, **kwargs):
    """print() that never raises on consoles that cannot encode emoji (e.g. cp1252)."""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        text = " ".join(str(a) for a in args).encode("ascii", "replace").decode("ascii")
        print(text, flush=kwargs.get("flush", False))


class ChatServer:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, show_plaintext: bool = True):
        self.host = host
        self.port = port
        self.show_plaintext = show_plaintext
        self.clients = {}  # name -> (JsonChannel, pubkey)
        self._lock = threading.Lock()
        self._sock = None
        self._running = False

    def start(self) -> None:
        """Bind, listen and accept clients on a background thread (port 0 picks a free port)."""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(5)
        self.port = self._sock.getsockname()[1]
        self._running = True
        _safe_print(f"[🖥️] Server running on {self.host}:{self.port}...\n", flush=True)
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def stop(self) -> None:
        self._running = False
        with self._lock:
            channels = [ch for ch, _ in self.clients.values()]
        for ch in channels:
            ch.close()
        if self._sock:
            self._sock.close()

    def serve_forever(self) -> None:
        self.start()
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            _safe_print("\n[!] Shutting down.")
        finally:
            self.stop()

    def _accept_loop(self) -> None:
        while self._running:
            try:
                conn, addr = self._sock.accept()
            except OSError:
                break
            threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()

    def _register(self, channel: JsonChannel, addr):
        """Handle the first message; return the client's name or None if rejected."""
        hello = channel.recv()
        name = (hello or {}).get("name", "")
        name = name.strip() if isinstance(name, str) else ""
        if not hello or hello.get("type") != "register" or not name:
            channel.send({"type": "error", "message": "expected a register message with a name"})
            return None
        try:
            validate_public_key(hello.get("pubkey"))
        except ValueError as e:
            channel.send({"type": "error", "message": f"invalid public key: {e}"})
            return None
        with self._lock:
            if name in self.clients:
                channel.send({"type": "error", "message": f"name '{name}' is already taken"})
                return None
            existing = list(self.clients.items())
            self.clients[name] = (channel, hello.get("pubkey"))
        channel.send({"type": "registered", "name": name})
        for peer, (_, key) in existing:
            channel.send({"type": "peer", "name": peer, "pubkey": key})
            self._safe_send(peer, {"type": "peer", "name": name, "pubkey": hello.get("pubkey")})
        _safe_print(f"[+] {name} connected from {addr}", flush=True)
        return name

    def _handle_client(self, conn, addr) -> None:
        channel = JsonChannel(conn)
        name = None
        try:
            name = self._register(channel, addr)
            while name:
                msg = channel.recv()
                if msg is None:
                    break
                if msg.get("type") == "message":
                    self._relay(name, msg, channel)
                elif msg.get("type") == "file":
                    self._relay_file(name, msg, channel)
        except (OSError, ValueError) as e:  # ValueError covers malformed JSON
            _safe_print(f"[x] Error handling client: {e}", flush=True)
        finally:
            if name:
                with self._lock:
                    self.clients.pop(name, None)
                    remaining = list(self.clients)
                for peer in remaining:
                    self._safe_send(peer, {"type": "peer_left", "name": name})
                _safe_print(f"[!] {name} disconnected.", flush=True)
            channel.close()

    def _relay(self, sender: str, msg: dict, channel: JsonChannel) -> None:
        receiver = msg.get("to")
        msg["from"] = sender  # never trust a client-supplied sender
        _safe_print(f"\n📩 Message from {sender} → {receiver}", flush=True)
        _safe_print(f"🔐 Algorithm: {msg.get('algorithm')}", flush=True)
        if self.show_plaintext and "original" in msg:
            _safe_print(f"📝 Original: {msg['original']}", flush=True)
        _safe_print(f"🧊 Encrypted: {summarize_cipher(msg.get('algorithm'), msg.get('encrypted'))}\n", flush=True)
        if not self._safe_send(receiver, msg):
            _safe_print(f"[!] Receiver {receiver} not connected.", flush=True)
            channel.send({"type": "error", "message": f"{receiver} is not connected"})

    def _relay_file(self, sender: str, msg: dict, channel: JsonChannel) -> None:
        receiver = msg.get("to")
        msg["from"] = sender
        _safe_print(f"\n🖼️ File from {sender} → {receiver}: {msg.get('filename')} "
              f"({msg.get('size')} bytes, {msg.get('algorithm')}, encrypted)\n", flush=True)
        if not self._safe_send(receiver, msg):
            _safe_print(f"[!] Receiver {receiver} not connected.", flush=True)
            channel.send({"type": "error", "message": f"{receiver} is not connected"})

    def _safe_send(self, name: str, obj: dict) -> bool:
        with self._lock:
            entry = self.clients.get(name)
        if not entry:
            return False
        try:
            entry[0].send(obj)
            return True
        except OSError:
            return False


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Secure Chat relay server")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--hide-plaintext", action="store_true", help="do not log the 'original' field")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ChatServer(args.host, args.port, show_plaintext=not args.hide_plaintext).serve_forever()


if __name__ == "__main__":
    main()
