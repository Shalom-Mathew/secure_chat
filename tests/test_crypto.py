import unittest

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


if __name__ == "__main__":
    unittest.main()
