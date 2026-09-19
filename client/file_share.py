"""Encrypted image sharing helpers.

Sending: validate an image, encrypt it, and pack it into a ``file`` message.
    * DES users encrypt the image with DES-CBC using the pre-shared key.
    * ElGamal users generate a random one-time DES session key, encrypt the image with it,
      and wrap only that small key with the recipient's ElGamal public key (hybrid
      encryption; encrypting megabytes with raw ElGamal would take minutes).
Receiving: decrypt, verify the SHA-256 checksum, re-validate the bytes as an image, and
save under a sanitised, non-clobbering filename.
"""

import base64
import hashlib
import os
import re

from Crypto.Random import get_random_bytes

from crypto.des_crypto import DESCipher

MAX_FILE_BYTES = 5 * 1024 * 1024
DEFAULT_DOWNLOAD_DIR = "received_files"

# detected type -> canonical extension
EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
              "image/bmp": ".bmp", "image/webp": ".webp"}
ALLOWED_INPUT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}


def detect_image_type(data: bytes):
    """Return the MIME type from magic bytes, or None if ``data`` is not a supported image."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"BM"):
        return "image/bmp"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def load_image(path: str):
    """Read and validate an image file; return ``(filename, mime, data)``."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in ALLOWED_INPUT_EXTENSIONS:
        raise ValueError(f"unsupported file type '{ext}' (allowed: {', '.join(sorted(ALLOWED_INPUT_EXTENSIONS))})")
    size = os.path.getsize(path)
    if size == 0:
        raise ValueError("file is empty")
    if size > MAX_FILE_BYTES:
        raise ValueError(f"file is too large ({size} bytes; limit is {MAX_FILE_BYTES})")
    with open(path, "rb") as f:
        data = f.read()
    mime = detect_image_type(data)
    if mime is None:
        raise ValueError("file content is not a supported image")
    return os.path.basename(path), mime, data


def pack_image(filename, data, algorithm, des: DESCipher, recipient_key=None, elgamal=None) -> dict:
    """Encrypt ``data`` and return the file-specific fields of a ``file`` message."""
    fields = {"filename": filename, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    if algorithm == "DES":
        blob = des.encrypt_bytes(data)
    else:
        session_key = get_random_bytes(8)
        blob = DESCipher(session_key).encrypt_bytes(data)
        fields["key"] = elgamal.encrypt_bytes(session_key, recipient_key)
    fields["encrypted"] = base64.b64encode(blob).decode("ascii")
    return fields


def unpack_image(info: dict, des: DESCipher, elgamal) -> bytes:
    """Decrypt a ``file`` message and verify size, checksum and image content."""
    blob = base64.b64decode(info["encrypted"])
    if info["algorithm"] == "DES":
        data = des.decrypt_bytes(blob)
    else:
        session_key = elgamal.decrypt_bytes(info["key"])
        data = DESCipher(session_key).decrypt_bytes(blob)
    if hashlib.sha256(data).hexdigest() != info.get("sha256"):
        raise ValueError("checksum mismatch: file was corrupted or tampered with")
    if len(data) > MAX_FILE_BYTES or detect_image_type(data) is None:
        raise ValueError("received file is not a valid image")
    return data


def safe_filename(name: str, mime: str) -> str:
    """Strip any path, keep a conservative stem, and use the extension of the detected type."""
    stem = os.path.splitext(os.path.basename(str(name).replace("\\", "/")))[0]
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", stem).strip("._") or "image"
    return stem[:80] + EXTENSIONS[mime]


def save_received(data: bytes, filename: str, directory: str = DEFAULT_DOWNLOAD_DIR) -> str:
    """Write ``data`` into ``directory`` without overwriting; return the saved path."""
    os.makedirs(directory, exist_ok=True)
    safe = safe_filename(filename, detect_image_type(data))
    stem, ext = os.path.splitext(safe)
    n = 0
    while True:
        path = os.path.join(directory, safe if n == 0 else f"{stem}_{n}{ext}")
        try:
            with open(path, "xb") as f:  # "x" fails if the file exists, so nothing is overwritten
                f.write(data)
            return path
        except FileExistsError:
            n += 1
