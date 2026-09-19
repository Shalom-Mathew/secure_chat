"""GUI tests: two real ChatGUI windows talking through a real server.

Skipped automatically when no display is available (e.g. headless CI).
"""

import contextlib
import io
import os
import tempfile
import time
import tkinter as tk
import unittest

from client.gui import ChatGUI
from server.server import ChatServer
from tests.test_file_share import make_png


def _display_available():
    try:
        root = tk.Tk()
        root.destroy()
        return True
    except tk.TclError:
        return False


@unittest.skipUnless(_display_available(), "no display available")
class GuiTests(unittest.TestCase):
    def setUp(self):
        self._log = contextlib.redirect_stdout(io.StringIO())
        self._log.__enter__()
        self.server = ChatServer("127.0.0.1", 0)
        self.server.start()
        self.root = tk.Tk()
        self.top = tk.Toplevel(self.root)
        self.alice, self.bob = ChatGUI(self.root), ChatGUI(self.top)
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        for gui in (self.alice, self.bob):
            gui.shutdown()
        self.server.stop()
        self.root.destroy()
        self.tmp.cleanup()
        self._log.__exit__(None, None, None)

    def pump(self, seconds=0.5, until=None):
        end = time.time() + seconds
        while time.time() < end:
            self.root.update()
            if until and until():
                return True
            time.sleep(0.01)
        return bool(until and until())

    def connect_both(self, algorithm):
        for gui, name in ((self.alice, "alice"), (self.bob, "bob")):
            gui.name_input.set(name)
            gui.server_input.set(f"127.0.0.1:{self.server.port}")
            gui.segment.set(algorithm, notify=True, animate=False)
            gui.client_download = os.path.join(self.tmp.name, name)
            gui.connect()
            self.assertIsNotNone(gui.client, gui.login_error.cget("text"))
            gui.client.download_dir = gui.client_download
        self.assertTrue(self.pump(3, lambda: self.alice.to_var.get() == "bob" and self.bob.to_var.get() == "alice"))

    def texts(self, gui):
        return [(r["side"], r["text"]) for r in gui.messages.records if r["kind"] == "bubble" and not r["path"]]

    def check_flow(self, algorithm):
        self.connect_both(algorithm)
        self.assertEqual(self.alice.client.algorithm_name, algorithm)
        self.alice.send_text("meet at 9. tell no one.")
        self.assertTrue(self.pump(3, lambda: ("in", "meet at 9. tell no one.") in self.texts(self.bob)))
        self.bob.send_text("understood")
        self.assertTrue(self.pump(3, lambda: ("in", "understood") in self.texts(self.alice)))
        # the ciphertext shown on both ends is identical, and is not the plaintext
        sent = next(r for r in self.alice.messages.records if r["side"] == "out")
        received = next(r for r in self.bob.messages.records if r["text"] == "meet at 9. tell no one.")
        self.assertEqual(sent["cipher"], received["cipher"])
        self.assertNotIn("meet", sent["cipher"])
        # image round trip with a preview on both sides
        path = os.path.join(self.tmp.name, "pic.png")
        with open(path, "wb") as f:
            f.write(make_png(120, 80))
        self.alice.attach(path)
        self.assertTrue(self.pump(5, lambda: any(r["path"] for r in self.bob.messages.records)))
        self.assertTrue(all(r["photo"] is not None for r in self.alice.messages.records if r["path"]))
        self.assertTrue(all(r["photo"] is not None for r in self.bob.messages.records if r["path"]))

    def test_des_flow(self):
        self.check_flow("DES")

    def test_elgamal_flow(self):
        self.check_flow("ElGamal")

    def test_switching_algorithm_live(self):
        self.connect_both("DES")
        self.alice.segment.set("ElGamal", notify=True, animate=False)
        self.assertEqual(self.alice.client.algorithm_name, "ElGamal")
        self.assertIn("ElGamal", self.alice.badge.text)
        self.alice.send_text("now with ElGamal")
        self.assertTrue(self.pump(3, lambda: ("in", "now with ElGamal") in self.texts(self.bob)))

    def test_long_input_stays_inside_the_box(self):
        self.connect_both("DES")
        self.root.update()
        self.alice.input.entry.focus_force()
        self.alice.input.set("typing a very long sentence that must never spill out of the text box " * 3)
        self.pump(0.3)
        entry_right = self.alice.input.entry.winfo_x() + self.alice.input.entry.winfo_width()
        self.assertLessEqual(entry_right, self.alice.input.winfo_width())
        self.assertGreater(len(self.alice.input.get()), self.alice.input.entry.winfo_width() // 8)

    def test_placeholder_never_counts_as_text(self):
        self.connect_both("DES")
        self.assertEqual(self.alice.input.get(), "")
        self.alice.send_text()  # empty placeholder must not send anything
        self.pump(0.3)
        self.assertEqual(self.texts(self.bob), [])

    def test_ciphertext_toggle(self):
        self.connect_both("DES")
        self.assertTrue(self.alice.messages.show_cipher)
        self.alice._toggle_cipher()
        self.assertFalse(self.alice.messages.show_cipher)

    def test_connect_errors_are_shown_inline(self):
        self.alice.name_input.set("")
        self.alice.connect()
        self.assertIn("name", self.alice.login_error.cget("text").lower())
        self.alice.name_input.set("alice")
        self.alice.server_input.set("127.0.0.1:1")  # nothing listens here
        self.alice.connect()
        self.assertIn("Could not connect", self.alice.login_error.cget("text"))
        self.assertIsNone(self.alice.client)


if __name__ == "__main__":
    unittest.main()
