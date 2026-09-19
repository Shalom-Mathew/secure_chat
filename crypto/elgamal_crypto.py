"""ElGamal public-key cipher over a fixed 2048-bit safe-prime group.

Every user shares the group ``(P, G)`` from ``elgamal_group`` and only generates a private
exponent ``x`` (public key ``y = G^x mod P``), so key generation is instant. Received public
keys are validated: a peer cannot make us encrypt in a weak group of its choosing.

Messages longer than one block are split into chunks. Each chunk is prefixed with a 0x01
byte so leading zero bytes survive the bytes<->integer round trip. Encrypted output is a
JSON-friendly list of ``[c1, c2]`` integer pairs.
"""

from Crypto.Random import random
from Crypto.Util.number import bytes_to_long, long_to_bytes

from crypto.elgamal_group import G, P

Q = (P - 1) // 2  # order of the subgroup; prime because P is a safe prime
CHUNK_SIZE = (P.bit_length() - 1) // 8 - 1  # chunk + 1 prefix byte is always < P (254 bytes)


def validate_public_key(public_key: dict) -> int:
    """Check ``public_key`` uses our group and a sane ``y``; return ``y`` as an int."""
    try:
        p, g, y = int(public_key["p"]), int(public_key["g"]), int(public_key["y"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("malformed ElGamal public key")
    if p != P or g != G:
        raise ValueError("ElGamal public key uses an unsupported group")
    if not 1 < y < P - 1:
        raise ValueError("invalid ElGamal public value")
    return y


class ElGamalCipher:
    def __init__(self):
        self.x = random.StrongRandom().randint(2, Q - 1)  # private exponent
        self.y = pow(G, self.x, P)

    @property
    def public_key(self) -> dict:
        """Public parameters ``{"p", "g", "y"}`` as plain ints (safe to send as JSON)."""
        return {"p": P, "g": G, "y": self.y}

    def encrypt(self, plaintext: str, public_key: dict = None) -> list:
        """Encrypt for ``public_key`` (defaults to this cipher's own public key)."""
        return self.encrypt_bytes(plaintext.encode("utf-8"), public_key)

    def decrypt(self, blocks: list) -> str:
        return self.decrypt_bytes(blocks).decode("utf-8")

    def encrypt_bytes(self, data: bytes, public_key: dict = None) -> list:
        y = validate_public_key(public_key or self.public_key)
        rng = random.StrongRandom()
        blocks = []
        for i in range(0, max(len(data), 1), CHUNK_SIZE):
            m = bytes_to_long(b"\x01" + data[i:i + CHUNK_SIZE])
            k = rng.randint(1, Q - 1)
            blocks.append([pow(G, k, P), (m * pow(y, k, P)) % P])
        return blocks

    def decrypt_bytes(self, blocks: list) -> bytes:
        data = b""
        for c1, c2 in blocks:
            c1, c2 = int(c1), int(c2)
            if not (0 < c1 < P and 0 < c2 < P):
                raise ValueError("ElGamal block out of range")
            m = (c2 * pow(pow(c1, self.x, P), -1, P)) % P
            chunk = long_to_bytes(m)
            if chunk[:1] != b"\x01":
                raise ValueError("ElGamal block was not encrypted for this key")
            data += chunk[1:]
        return data
