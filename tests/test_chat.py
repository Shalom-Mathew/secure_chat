"""End-to-end tests: a real ChatServer on a free port with real ChatClients."""

import contextlib
import io
import queue
import unittest

from client.client import ChatClient
from server.server import ChatServer


def make_client(server, name, algorithm, **kw):
    client = ChatClient(name, algorithm, "127.0.0.1", server.port, **kw)
    client.inbox = queue.Queue()
    client.errors = queue.Queue()
    client.receiver_callback = lambda sender, text: client.inbox.put((sender, text))
    client.error_callback = client.errors.put
    client.connect()
    return client


class ChatTests(unittest.TestCase):
    def setUp(self):
        self.log = io.StringIO()
        self._redirect = contextlib.redirect_stdout(self.log)
        self._redirect.__enter__()
        self.server = ChatServer("127.0.0.1", 0)
        self.server.start()
        self.clients = []

    def tearDown(self):
        for c in self.clients:
            c.disconnect()
        self.server.stop()
        self._redirect.__exit__(None, None, None)

    def connect(self, name, algorithm, **kw):
        c = make_client(self.server, name, algorithm, **kw)
        self.clients.append(c)
        return c

    def test_des_message_between_clients(self):
        alice, bob = self.connect("alice", "DES"), self.connect("bob", "DES")
        alice.send_message("bob", "hello bob")
        self.assertEqual(bob.inbox.get(timeout=5), ("alice", "hello bob"))

    def test_elgamal_message_between_clients(self):
        alice, bob = self.connect("alice", "ElGamal"), self.connect("bob", "ElGamal")
        self.assertTrue(alice.wait_for_peer("bob"))
        alice.send_message("bob", "meet at 9. tell no one.")
        self.assertEqual(bob.inbox.get(timeout=5), ("alice", "meet at 9. tell no one."))

    def test_elgamal_long_message_and_reply(self):
        alice, bob = self.connect("alice", "ElGamal"), self.connect("bob", "ElGamal")
        self.assertTrue(alice.wait_for_peer("bob") and bob.wait_for_peer("alice"))
        long_text = "long message 🔐 " * 30
        alice.send_message("bob", long_text)
        self.assertEqual(bob.inbox.get(timeout=5), ("alice", long_text))
        bob.send_message("alice", "got it")
        self.assertEqual(alice.inbox.get(timeout=5), ("bob", "got it"))

    def test_mixed_algorithms(self):
        alice, bob = self.connect("alice", "ElGamal"), self.connect("bob", "DES")
        self.assertTrue(alice.wait_for_peer("bob"))
        alice.send_message("bob", "elgamal to des user")
        self.assertEqual(bob.inbox.get(timeout=5), ("alice", "elgamal to des user"))
        bob.send_message("alice", "des to elgamal user")
        self.assertEqual(alice.inbox.get(timeout=5), ("bob", "des to elgamal user"))

    def test_rapid_messages_are_framed_correctly(self):
        alice, bob = self.connect("alice", "DES"), self.connect("bob", "DES")
        for i in range(50):
            alice.send_message("bob", f"msg {i}")
        received = [bob.inbox.get(timeout=5)[1] for _ in range(50)]
        self.assertEqual(received, [f"msg {i}" for i in range(50)])

    def test_duplicate_name_rejected(self):
        self.connect("alice", "DES")
        with self.assertRaises(ConnectionError):
            make_client(self.server, "alice", "DES")

    def test_empty_name_rejected(self):
        with self.assertRaises(ConnectionError):
            make_client(self.server, "   ", "DES")

    def test_offline_recipient_reports_error(self):
        alice = self.connect("alice", "DES")
        alice.send_message("ghost", "anyone there?")
        self.assertIn("ghost is not connected", alice.errors.get(timeout=5))

    def test_elgamal_to_unknown_peer_raises(self):
        alice = self.connect("alice", "ElGamal")
        with self.assertRaises(ValueError):
            alice.send_message("ghost", "hi")

    def test_peer_leaves_and_name_is_reusable(self):
        alice, bob = self.connect("alice", "ElGamal"), self.connect("bob", "ElGamal")
        self.assertTrue(alice.wait_for_peer("bob"))
        bob.disconnect()
        for _ in range(100):
            if "bob" not in alice.peers:
                break
            import time
            time.sleep(0.05)
        self.assertNotIn("bob", alice.peers)
        self.connect("bob", "DES")

    def test_server_log_shows_original_and_encrypted(self):
        alice, bob = self.connect("alice", "DES"), self.connect("bob", "DES")
        alice.send_message("bob", "visible in log")
        bob.inbox.get(timeout=5)
        self.assertIn("📝 Original: visible in log", self.log.getvalue())
        self.assertIn("🧊 Encrypted:", self.log.getvalue())

    def test_plaintext_can_be_withheld(self):
        alice, bob = self.connect("alice", "DES", send_plaintext=False), self.connect("bob", "DES")
        alice.send_message("bob", "private text")
        self.assertEqual(bob.inbox.get(timeout=5), ("alice", "private text"))
        self.assertNotIn("private text", self.log.getvalue())


if __name__ == "__main__":
    unittest.main()
