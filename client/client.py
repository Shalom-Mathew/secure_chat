"""Network handler for the chat client (registration, key exchange, encrypt/decrypt)."""

import socket
import threading
import time

from client import file_share
from common.utils import DEFAULT_HOST, DEFAULT_PORT, JsonChannel, get_des_key, summarize_cipher
from crypto.des_crypto import DESCipher
from crypto.elgamal_crypto import ElGamalCipher

ALGORITHMS = ("DES", "ElGamal")
ALGORITHM_LABELS = {"DES": "DES-CBC · 56-bit", "ElGamal": "ElGamal · 2048-bit"}


class ChatClient:
    def __init__(self, name, algorithm, server_host=DEFAULT_HOST, server_port=DEFAULT_PORT,
                 des_key=None, send_plaintext=True, download_dir=file_share.DEFAULT_DOWNLOAD_DIR):
        if algorithm not in ALGORITHMS:
            raise ValueError("Unsupported algorithm")
        self.name = name
        self.algorithm_name = algorithm
        self.server_host = server_host
        self.server_port = server_port
        self.send_plaintext = send_plaintext  # the server logs 'original' when present
        self.receiver_callback = None  # callback(sender, message) — used by the GUI
        self.error_callback = None     # callback(text)
        self.file_callback = None      # callback(sender, saved_path)
        self.cipher_callback = None    # callback(direction "in"/"out", peer, ciphertext_summary)
        self.peers_callback = None     # callback() when the online-peer list changes
        self.download_dir = download_dir
        self.last_incoming_algorithm = None  # algorithm of the most recent message/file received
        self.peers = {}                # name -> ElGamal public key
        self._peers_lock = threading.Lock()
        self.des = DESCipher(des_key or get_des_key())
        self.elgamal = ElGamalCipher()
        self.channel = None

    def connect(self) -> None:
        sock = socket.create_connection((self.server_host, self.server_port), timeout=10)
        sock.settimeout(None)
        self.channel = JsonChannel(sock)
        self.channel.send({"type": "register", "name": self.name, "pubkey": self.elgamal.public_key})
        reply = self.channel.recv()
        if not reply or reply.get("type") != "registered":
            self.channel.close()
            raise ConnectionError((reply or {}).get("message", "server closed the connection"))
        threading.Thread(target=self.listen_for_messages, daemon=True).start()

    def disconnect(self) -> None:
        if self.channel:
            self.channel.close()

    def set_algorithm(self, algorithm) -> None:
        """Switch the algorithm used for messages and images sent from now on."""
        if algorithm not in ALGORITHMS:
            raise ValueError("Unsupported algorithm")
        self.algorithm_name = algorithm

    def online_peers(self) -> list:
        with self._peers_lock:
            return sorted(self.peers)

    def send_message(self, to, message) -> str:
        if self.algorithm_name == "DES":
            encrypted = self.des.encrypt(message)
        else:
            with self._peers_lock:
                key = self.peers.get(to)
            if key is None:
                raise ValueError(f"{to} is not connected")
            encrypted = self.elgamal.encrypt(message, key)
        data = {"type": "message", "from": self.name, "to": to,
                "algorithm": self.algorithm_name, "encrypted": encrypted}
        if self.send_plaintext:
            data["original"] = message
        self.channel.send(data)
        summary = summarize_cipher(self.algorithm_name, encrypted)
        if self.cipher_callback:
            self.cipher_callback("out", to, summary)
        return summary

    def send_image(self, to, path) -> str:
        """Encrypt and send an image file (png/jpg/gif/bmp/webp, up to 5 MB) to ``to``."""
        filename, mime, data = file_share.load_image(path)
        key = None
        if self.algorithm_name == "ElGamal":
            with self._peers_lock:
                key = self.peers.get(to)
            if key is None:
                raise ValueError(f"{to} is not connected")
        fields = file_share.pack_image(filename, data, self.algorithm_name, self.des, key, self.elgamal)
        self.channel.send({"type": "file", "from": self.name, "to": to,
                           "algorithm": self.algorithm_name, "mime": mime, **fields})
        summary = f"{fields['size']:,} bytes, encrypted"
        if self.cipher_callback:
            self.cipher_callback("out", to, summary)
        return summary

    def wait_for_peer(self, name, timeout=5.0) -> bool:
        """Block until ``name`` shows up in the peer directory (used by tests/scripts)."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self._peers_lock:
                if name in self.peers:
                    return True
            time.sleep(0.02)
        return False

    def _decrypt(self, info) -> str:
        if info["algorithm"] == "DES":
            return self.des.decrypt(info["encrypted"])
        return self.elgamal.decrypt(info["encrypted"])

    def listen_for_messages(self) -> None:
        while True:
            try:
                info = self.channel.recv()
                if info is None:
                    break
                kind = info.get("type")
                if kind == "peer":
                    with self._peers_lock:
                        self.peers[info["name"]] = info["pubkey"]
                    self._peers_changed()
                elif kind == "peer_left":
                    with self._peers_lock:
                        self.peers.pop(info["name"], None)
                    self._peers_changed()
                elif kind == "error":
                    self._report(info.get("message", "server error"))
                elif kind == "file":
                    self.last_incoming_algorithm = info.get("algorithm")
                    data = file_share.unpack_image(info, self.des, self.elgamal)
                    if self.cipher_callback:
                        self.cipher_callback("in", info["from"], f"{len(data):,} bytes, decrypted")
                    saved = file_share.save_received(data, info.get("filename", "image"), self.download_dir)
                    if self.file_callback:
                        self.file_callback(info["from"], saved)
                elif kind == "message":
                    self.last_incoming_algorithm = info.get("algorithm")
                    text = self._decrypt(info)
                    if self.cipher_callback:
                        self.cipher_callback("in", info["from"], summarize_cipher(info["algorithm"], info["encrypted"]))
                    if self.receiver_callback:
                        self.receiver_callback(info["from"], text)
            except OSError:
                break
            except Exception as e:  # a bad message must not kill the listener
                self._report(f"could not process incoming message: {e}")

    def _peers_changed(self) -> None:
        if self.peers_callback:
            self.peers_callback()

    def _report(self, text) -> None:
        if self.error_callback:
            self.error_callback(text)
        else:
            print(f"[x] {text}")
