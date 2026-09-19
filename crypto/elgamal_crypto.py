"""ElGamal public-key cipher.

Messages longer than one block are split into chunks. Each chunk is prefixed with a
0x01 byte so leading zero bytes survive the bytes<->integer round trip. Encrypted
output is a JSON-friendly list of ``[c1, c2]`` integer pairs.
"""

from Crypto.PublicKey import ElGamal
from Crypto.Random import get_random_bytes, random
from Crypto.Util.number import GCD, bytes_to_long, long_to_bytes


class ElGamalCipher:
    def __init__(self, key_length: int = 256):
        self.key = ElGamal.generate(key_length, get_random_bytes)

    @property
    def public_key(self) -> dict:
        """Public parameters ``{"p", "g", "y"}`` as plain ints (safe to send as JSON)."""
        return {"p": int(self.key.p), "g": int(self.key.g), "y": int(self.key.y)}

    def encrypt(self, plaintext: str, public_key: dict = None) -> list:
        """Encrypt for ``public_key`` (defaults to this cipher's own public key)."""
        return self.encrypt_bytes(plaintext.encode("utf-8"), public_key)

    def decrypt(self, blocks: list) -> str:
        return self.decrypt_bytes(blocks).decode("utf-8")

    def encrypt_bytes(self, data: bytes, public_key: dict = None) -> list:
        pk = public_key or self.public_key
        p, g, y = int(pk["p"]), int(pk["g"]), int(pk["y"])
        chunk_size = (p.bit_length() - 1) // 8 - 1  # chunk + 1 prefix byte is always < p
        blocks = []
        for i in range(0, max(len(data), 1), chunk_size):
            m = bytes_to_long(b"\x01" + data[i:i + chunk_size])
            while True:
                k = random.StrongRandom().randint(1, p - 2)
                if GCD(k, p - 1) == 1:
                    break
            blocks.append([pow(g, k, p), (m * pow(y, k, p)) % p])
        return blocks

    def decrypt_bytes(self, blocks: list) -> bytes:
        p, x = int(self.key.p), int(self.key.x)
        data = b""
        for c1, c2 in blocks:
            s = pow(int(c1), x, p)
            m = (int(c2) * pow(s, -1, p)) % p
            chunk = long_to_bytes(m)
            if chunk[:1] != b"\x01":
                raise ValueError("ElGamal block was not encrypted for this key")
            data += chunk[1:]
        return data
