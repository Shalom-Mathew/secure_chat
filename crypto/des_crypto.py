"""DES (ECB) symmetric cipher with PKCS#7 padding and base64 output."""

import base64

from Crypto.Cipher import DES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad


class DESCipher:
    def __init__(self, key: bytes = b"secret12"):
        self.key = key[:8].ljust(8, b"0")  # DES requires an 8-byte key
        self.cipher = DES.new(self.key, DES.MODE_ECB)

    def encrypt(self, plaintext: str) -> str:
        padded = pad(plaintext.encode("utf-8"), DES.block_size)
        return base64.b64encode(self.cipher.encrypt(padded)).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        decrypted = self.cipher.decrypt(base64.b64decode(ciphertext.encode("utf-8")))
        return unpad(decrypted, DES.block_size).decode("utf-8")

    # --- binary payloads (files) use CBC with a random IV so identical blocks do not leak ---

    def encrypt_bytes(self, data: bytes) -> bytes:
        """Encrypt raw bytes with DES-CBC; returns ``iv + ciphertext``."""
        iv = get_random_bytes(DES.block_size)
        return iv + DES.new(self.key, DES.MODE_CBC, iv).encrypt(pad(data, DES.block_size))

    def decrypt_bytes(self, blob: bytes) -> bytes:
        iv, body = blob[:DES.block_size], blob[DES.block_size:]
        return unpad(DES.new(self.key, DES.MODE_CBC, iv).decrypt(body), DES.block_size)
