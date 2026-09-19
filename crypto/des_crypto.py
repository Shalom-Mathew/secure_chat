"""DES symmetric cipher (CBC mode, random IV per message, PKCS#7 padding).

DES is obsolete (56-bit key) and is used here for coursework. CBC with a fresh IV means the
same plaintext never produces the same ciphertext and repeated blocks do not leak, which the
previous ECB mode could not guarantee.
"""

import base64

from Crypto.Cipher import DES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad


class DESCipher:
    def __init__(self, key: bytes = b"secret12"):
        self.key = key[:8].ljust(8, b"0")  # DES requires an 8-byte key

    def encrypt_bytes(self, data: bytes) -> bytes:
        """Encrypt raw bytes; returns ``iv + ciphertext``."""
        iv = get_random_bytes(DES.block_size)
        return iv + DES.new(self.key, DES.MODE_CBC, iv).encrypt(pad(data, DES.block_size))

    def decrypt_bytes(self, blob: bytes) -> bytes:
        iv, body = blob[:DES.block_size], blob[DES.block_size:]
        return unpad(DES.new(self.key, DES.MODE_CBC, iv).decrypt(body), DES.block_size)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt text; returns base64 of ``iv + ciphertext``."""
        return base64.b64encode(self.encrypt_bytes(plaintext.encode("utf-8"))).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        return self.decrypt_bytes(base64.b64decode(ciphertext.encode("ascii"))).decode("utf-8")
