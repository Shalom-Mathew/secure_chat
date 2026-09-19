import unittest

from Crypto.Util.number import isPrime

from crypto import elgamal_crypto
from crypto.des_crypto import DESCipher
from crypto.elgamal_crypto import ElGamalCipher


class DESTests(unittest.TestCase):
    def test_round_trip(self):
        des = DESCipher(b"secret12")
        for text in ["Hello from DES", "", "ünïcödé 🔐", "x" * 1000]:
            self.assertEqual(des.decrypt(des.encrypt(text)), text)

    def test_same_key_interoperates(self):
        self.assertEqual(DESCipher(b"secret12").decrypt(DESCipher(b"secret12").encrypt("hi")), "hi")

    def test_ciphertext_differs_from_plaintext(self):
        self.assertNotIn("Hello", DESCipher().encrypt("Hello"))

    def test_encryption_is_randomized(self):
        des = DESCipher()
        self.assertNotEqual(des.encrypt("same"), des.encrypt("same"))

    def test_repeated_blocks_do_not_repeat_in_ciphertext(self):
        import base64
        blob = base64.b64decode(DESCipher().encrypt("A" * 64))
        blocks = [blob[i:i + 8] for i in range(8, len(blob), 8)]
        self.assertEqual(len(blocks), len(set(blocks)))  # CBC: no identical blocks (ECB would repeat)

    def test_short_key_is_padded(self):
        des = DESCipher(b"abc")
        self.assertEqual(des.decrypt(des.encrypt("ok")), "ok")


class ElGamalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.alice = ElGamalCipher()
        cls.bob = ElGamalCipher()

    def test_round_trip_own_key(self):
        self.assertEqual(self.alice.decrypt(self.alice.encrypt("Hello from ElGamal")), "Hello from ElGamal")

    def test_encrypt_for_other_public_key(self):
        blocks = self.alice.encrypt("meet at 9", self.bob.public_key)
        self.assertEqual(self.bob.decrypt(blocks), "meet at 9")

    def test_wrong_key_cannot_decrypt(self):
        blocks = self.alice.encrypt("secret", self.bob.public_key)
        try:
            result = self.alice.decrypt(blocks)
        except (ValueError, UnicodeDecodeError):
            return
        self.assertNotEqual(result, "secret")

    def test_long_and_unicode_messages(self):
        for text in ["a" * 500, "ünïcödé 🔐 " * 20, "", "\x00leading nul"]:
            self.assertEqual(self.bob.decrypt(self.alice.encrypt(text, self.bob.public_key)), text)

    def test_public_key_is_json_safe(self):
        import json
        self.assertEqual(json.loads(json.dumps(self.alice.public_key)), self.alice.public_key)

    def test_encryption_is_randomized(self):
        self.assertNotEqual(self.alice.encrypt("same"), self.alice.encrypt("same"))

    def test_group_is_a_2048_bit_safe_prime(self):
        self.assertEqual(elgamal_crypto.P.bit_length(), 2048)
        self.assertTrue(isPrime(elgamal_crypto.P))
        self.assertTrue(isPrime(elgamal_crypto.Q))

    def test_rejects_public_keys_from_a_foreign_group(self):
        bad = dict(self.bob.public_key, p=23, g=5, y=8)
        with self.assertRaises(ValueError):
            self.alice.encrypt("x", bad)
        for y in (0, 1, elgamal_crypto.P - 1):
            with self.assertRaises(ValueError):
                self.alice.encrypt("x", dict(self.bob.public_key, y=y))
        with self.assertRaises(ValueError):
            self.alice.encrypt("x", {"p": "junk"})

    def test_multi_chunk_message(self):
        text = "z" * (elgamal_crypto.CHUNK_SIZE * 3 + 5)
        blocks = self.alice.encrypt(text, self.bob.public_key)
        self.assertEqual(len(blocks), 4)
        self.assertEqual(self.bob.decrypt(blocks), text)

    def test_key_generation_is_fast(self):
        import time
        start = time.monotonic()
        for _ in range(5):
            ElGamalCipher()
        self.assertLess(time.monotonic() - start, 2.0)


if __name__ == "__main__":
    unittest.main()
