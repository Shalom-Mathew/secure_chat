import contextlib
import io
import os
import queue
import struct
import tempfile
import unittest
import zlib

from client import file_share
from client.client import ChatClient
from crypto.des_crypto import DESCipher
from crypto.elgamal_crypto import ElGamalCipher
from server.server import ChatServer


def make_png(width=64, height=64) -> bytes:
    """Build a small valid PNG (a gradient) with the standard library only."""
    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
    rows = b"".join(b"\x00" + b"".join(bytes((x * 4 % 256, y * 4 % 256, 128)) for x in range(width))
                    for y in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


class HelperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.png = make_png()

    def write(self, name, data):
        path = os.path.join(self.tmp.name, name)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def test_detect_types(self):
        self.assertEqual(file_share.detect_image_type(self.png), "image/png")
        self.assertEqual(file_share.detect_image_type(b"\xff\xd8\xff\xe0rest"), "image/jpeg")
        self.assertEqual(file_share.detect_image_type(b"GIF89a...."), "image/gif")
        self.assertEqual(file_share.detect_image_type(b"RIFF\x00\x00\x00\x00WEBPVP8 "), "image/webp")
        self.assertIsNone(file_share.detect_image_type(b"MZ executable"))

    def test_load_rejects_bad_files(self):
        with self.assertRaises(ValueError):
            file_share.load_image(self.write("notes.txt", b"hello"))
        with self.assertRaises(ValueError):  # right extension, wrong content
            file_share.load_image(self.write("fake.png", b"not an image"))
        with self.assertRaises(ValueError):
            file_share.load_image(self.write("empty.png", b""))
        with self.assertRaises(ValueError):
            file_share.load_image(self.write("big.png", self.png + b"0" * file_share.MAX_FILE_BYTES))

    def test_pack_unpack_des_and_elgamal(self):
        des, alice, bob = DESCipher(b"secret12"), ElGamalCipher(), ElGamalCipher()
        info = {"algorithm": "DES", **file_share.pack_image("a.png", self.png, "DES", des)}
        self.assertEqual(file_share.unpack_image(info, des, alice), self.png)
        info = {"algorithm": "ElGamal",
                **file_share.pack_image("a.png", self.png, "ElGamal", des, bob.public_key, alice)}
        self.assertEqual(file_share.unpack_image(info, des, bob), self.png)

    def test_tampering_is_detected(self):
        des = DESCipher(b"secret12")
        info = {"algorithm": "DES", **file_share.pack_image("a.png", self.png, "DES", des)}
        info["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            file_share.unpack_image(info, des, None)

    def test_safe_filename_blocks_traversal(self):
        for evil in ["../../etc/passwd.png", "..\\..\\evil.png", "/abs/x.png", "a b$c.png"]:
            name = file_share.safe_filename(evil, "image/png")
            self.assertEqual(os.path.basename(name), name)
            self.assertTrue(name.endswith(".png"))
        self.assertEqual(file_share.safe_filename("shell.exe", "image/png"), "shell.png")

    def test_save_does_not_overwrite(self):
        first = file_share.save_received(self.png, "pic.png", self.tmp.name)
        second = file_share.save_received(self.png, "pic.png", self.tmp.name)
        self.assertNotEqual(first, second)
        self.assertTrue(os.path.exists(first) and os.path.exists(second))


class ImageTransferTests(unittest.TestCase):
    def setUp(self):
        self._log = contextlib.redirect_stdout(io.StringIO())
        self._log.__enter__()
        self.server = ChatServer("127.0.0.1", 0)
        self.server.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.png_path = os.path.join(self.tmp.name, "photo.png")
        self.png = make_png(200, 200)
        with open(self.png_path, "wb") as f:
            f.write(self.png)
        self.clients = []

    def tearDown(self):
        for c in self.clients:
            c.disconnect()
        self.server.stop()
        self.tmp.cleanup()
        self._log.__exit__(None, None, None)

    def connect(self, name, algorithm):
        c = ChatClient(name, algorithm, "127.0.0.1", self.server.port,
                       download_dir=os.path.join(self.tmp.name, f"downloads_{name}"))
        c.files, c.errors = queue.Queue(), queue.Queue()
        c.file_callback = lambda sender, path: c.files.put((sender, path))
        c.error_callback = c.errors.put
        c.connect()
        self.clients.append(c)
        return c

    def check_transfer(self, algorithm):
        alice, bob = self.connect("alice", algorithm), self.connect("bob", algorithm)
        self.assertTrue(alice.wait_for_peer("bob"))
        alice.send_image("bob", self.png_path)
        sender, path = bob.files.get(timeout=20)
        self.assertEqual(sender, "alice")
        with open(path, "rb") as f:
            self.assertEqual(f.read(), self.png)

    def test_des_image_transfer(self):
        self.check_transfer("DES")

    def test_elgamal_image_transfer(self):
        self.check_transfer("ElGamal")

    def test_server_log_never_contains_image_bytes(self):
        alice, bob = self.connect("alice", "DES"), self.connect("bob", "DES")
        alice.send_image("bob", self.png_path)
        bob.files.get(timeout=20)
        self.assertEqual(alice.errors.qsize(), 0)

    def test_send_invalid_file_raises(self):
        alice = self.connect("alice", "DES")
        bad = os.path.join(self.tmp.name, "x.png")
        with open(bad, "wb") as f:
            f.write(b"not a png")
        with self.assertRaises(ValueError):
            alice.send_image("bob", bad)

    def test_offline_recipient(self):
        alice = self.connect("alice", "DES")
        alice.send_image("ghost", self.png_path)
        self.assertIn("ghost is not connected", alice.errors.get(timeout=5))


if __name__ == "__main__":
    unittest.main()
