"""Dark-themed Tkinter front end.  Run with:  python -m client.gui"""

import queue
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, ttk

from client import theme as T
from client.client import ALGORITHM_LABELS, ALGORITHMS, ChatClient
from client.widgets import MessageList, PillButton, PillEntry, Segmented
from common.utils import DEFAULT_HOST, DEFAULT_PORT

AVATAR_COLORS = ("#2563eb", "#059669", "#7c3aed", "#db2777", "#d97706", "#0891b2")
IMAGE_TYPES = [("Images", "*.png *.jpg *.jpeg *.gif *.bmp *.webp")]


class ChatGUI:
    WIDTH, HEIGHT = 520, 640

    def __init__(self, master=None):
        self.own_root = master is None
        self.root = master or tk.Tk()
        self.root.title("🔐 Secure Chat")
        self.root.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.root.minsize(460, 560)
        self.root.configure(bg=T.BG)
        self.client = None
        self.events = queue.Queue()  # network threads -> Tk main thread
        self.algorithm = ALGORITHMS[0]
        self._last_in_cipher = None
        self._status_job = None
        self._poll_job = None
        self._make_fonts()
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._poll_job = self.root.after(50, self._poll)

    # ------------------------------------------------------------------ layout
    def _make_fonts(self):
        family = T.pick_font(self.root, T.FONT_CANDIDATES, "TkDefaultFont")
        mono = T.pick_font(self.root, T.MONO_CANDIDATES, "TkFixedFont")
        self.f_body = tkfont.Font(root=self.root, family=family, size=13)
        self.f_small = tkfont.Font(root=self.root, family=family, size=10)
        self.f_bold = tkfont.Font(root=self.root, family=family, size=11, weight="bold")
        self.f_name = tkfont.Font(root=self.root, family=family, size=15, weight="bold")
        self.f_title = tkfont.Font(root=self.root, family=family, size=18, weight="bold")
        self.f_mono = tkfont.Font(root=self.root, family=mono, size=10)

    def _build(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Dark.TCombobox", fieldbackground=T.INPUT, background=T.SURFACE2, foreground=T.TEXT,
                        bordercolor=T.BORDER, lightcolor=T.INPUT, darkcolor=T.INPUT, arrowcolor=T.MUTED,
                        selectbackground=T.INPUT, selectforeground=T.TEXT, padding=6)
        style.map("Dark.TCombobox", fieldbackground=[("readonly", T.INPUT)], foreground=[("readonly", T.TEXT)],
                  bordercolor=[("focus", T.BLUE)])
        self.root.option_add("*TCombobox*Listbox.background", T.SURFACE2)
        self.root.option_add("*TCombobox*Listbox.foreground", T.TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", T.GREEN_DK)

        self.card = tk.Frame(self.root, bg=T.SURFACE, highlightthickness=1, highlightbackground=T.BORDER)
        self.card.pack(fill="both", expand=True, padx=T.SP2, pady=T.SP2)
        self._build_header()
        self._build_options()
        self._build_composer()  # packed at the bottom before the chat so it keeps its space
        self.messages = MessageList(self.card, self.f_body, self.f_small, self.f_mono)
        self.messages.pack(fill="both", expand=True)
        self._build_login()
        self._set_chat_enabled(False)

    def _build_header(self):
        header = tk.Frame(self.card, bg=T.SURFACE, height=66)
        header.pack(fill="x")
        header.pack_propagate(False)
        self.avatar = tk.Canvas(header, width=44, height=44, bg=T.SURFACE, highlightthickness=0)
        self.avatar.place(x=T.SP3, y=11)
        self._draw_avatar("?", "#475569")
        self.name_label = tk.Label(header, text="Not connected", font=self.f_name, fg=T.TEXT, bg=T.SURFACE)
        self.name_label.place(x=T.SP3 + 56, y=8)
        self.status_label = tk.Label(header, text="● offline", font=self.f_small, fg=T.MUTED, bg=T.SURFACE)
        self.status_label.place(x=T.SP3 + 56, y=36)
        self.badge = PillButton(header, ALGORITHM_LABELS[self.algorithm], None, 172, 32, T.GREEN_BG, T.GREEN_TX,
                                self.f_small, parent_bg=T.SURFACE)
        self.badge.place(relx=1.0, x=-T.SP3, y=17, anchor="ne")
        self.badge.configure(cursor="arrow")
        tk.Frame(self.card, bg=T.BORDER, height=1).pack(fill="x")

    def _build_options(self):
        bar = tk.Frame(self.card, bg=T.SURFACE, height=56)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        self.segment = Segmented(bar, ALGORITHMS, self.on_algorithm, self.f_bold)
        self.segment.pack(side="left", padx=(T.SP3, T.SP1), pady=11)
        self.to_var = tk.StringVar()
        self.to_box = ttk.Combobox(bar, textvariable=self.to_var, state="readonly", width=6,
                                   style="Dark.TCombobox", font=self.f_small, values=[])
        self.to_box.pack(side="left", padx=T.SP1, pady=11)
        self.cipher_chip = PillButton(bar, "Ciphertext", self._toggle_cipher, 92, 34, T.GREEN_BG, T.GREEN_TX,
                                      self.f_small, outline=T.GREEN_LINE)
        self.cipher_chip.pack(side="left", padx=T.SP1, pady=11)
        self.attach_chip = PillButton(bar, "Attach", self.attach, 66, 34, T.SURFACE2, "#c7d3df",
                                      self.f_small, outline=T.BORDER)
        self.attach_chip.pack(side="left", padx=(0, T.SP1), pady=11)
        tk.Frame(self.card, bg=T.BORDER, height=1).pack(fill="x")
        self.show_cipher = True

    def _build_composer(self):
        bottom = tk.Frame(self.card, bg=T.SURFACE)
        bottom.pack(side="bottom", fill="x")
        self.status = tk.Label(bottom, text="", font=self.f_small, fg=T.GREEN_TX, bg=T.SURFACE, anchor="w")
        self.status.pack(fill="x", padx=T.SP3, pady=(T.SP1, 0))
        row = tk.Frame(bottom, bg=T.SURFACE)
        row.pack(fill="x", padx=T.SP3, pady=(T.SP1, T.SP2))
        self.input = PillEntry(row, self.f_body, "Message…", width=300, height=46, on_submit=self.send_text)
        self.input.pack(side="left", fill="x", expand=True)
        self.send_button = PillButton(row, "Send ➤", self.send_text, 92, 46, T.BLUE, "#ffffff", self.f_bold,
                                      hover=T.BLUE_HOVER)
        self.send_button.pack(side="left", padx=(T.SP1, 0))

    def _build_login(self):
        self.login = tk.Frame(self.messages, bg=T.SURFACE2, highlightthickness=1, highlightbackground=T.BORDER)
        self.login.place(relx=0.5, rely=0.42, anchor="center", width=380)
        tk.Label(self.login, text="Join the conversation", font=self.f_title, fg=T.TEXT, bg=T.SURFACE2).pack(
            anchor="w", padx=T.SP3, pady=(T.SP3, 0))
        tk.Label(self.login, text="Pick a name, choose an algorithm above, then connect.", font=self.f_small,
                 fg=T.MUTED, bg=T.SURFACE2).pack(anchor="w", padx=T.SP3, pady=(2, T.SP2))
        self.name_input = self._labeled_input("Your name", "alice")
        self.server_input = self._labeled_input("Server", f"{DEFAULT_HOST}:{DEFAULT_PORT}", prefill=True)
        self.login_error = tk.Label(self.login, text="", font=self.f_small, fg=T.RED, bg=T.SURFACE2, anchor="w",
                                    wraplength=330, justify="left")
        self.login_error.pack(fill="x", padx=T.SP3)
        self.connect_button = PillButton(self.login, "Connect", self.connect, 332, 44, T.BLUE, "#ffffff",
                                         self.f_bold, parent_bg=T.SURFACE2, hover=T.BLUE_HOVER)
        self.connect_button.pack(padx=T.SP3, pady=(T.SP1, T.SP3))
        self.name_input.entry.focus_set()

    def _labeled_input(self, label, placeholder, prefill=False):
        tk.Label(self.login, text=label, font=self.f_small, fg=T.MUTED, bg=T.SURFACE2, anchor="w").pack(
            fill="x", padx=T.SP3)
        field = PillEntry(self.login, self.f_body, placeholder, width=332, height=42, parent_bg=T.SURFACE2,
                          on_submit=self.connect)
        field.pack(padx=T.SP3, pady=(4, T.SP2))
        if prefill:
            field.set(placeholder)
        return field

    # ---------------------------------------------------------------- helpers
    def _draw_avatar(self, letter, color):
        self.avatar.delete("all")
        self.avatar.create_oval(1, 1, 43, 43, fill=color, outline="")
        self.avatar.create_text(22, 22, text=letter.upper(), fill="#ffffff", font=self.f_name)

    def _set_chat_enabled(self, enabled):
        self.input.set_enabled(enabled)
        self.send_button.set_enabled(enabled)
        self.attach_chip.set_enabled(enabled)
        self.to_box.configure(state="readonly" if enabled else "disabled")

    def _flash_status(self, text, color=T.GREEN_TX):
        self.status.configure(text=text, fg=color)
        if self._status_job:
            self.root.after_cancel(self._status_job)
        self._status_job = self.root.after(4000, lambda: self.status.configure(text=""))

    def _refresh_badge(self):
        self.badge.restyle(text=ALGORITHM_LABELS[self.algorithm])

    # ---------------------------------------------------------------- actions
    def connect(self):
        name = self.name_input.get().strip()
        host, _, port = self.server_input.get().strip().partition(":")
        self.name_input.set_error(not name)
        if not name:
            self.login_error.configure(text="Please enter a name.")
            return
        try:
            self.client = ChatClient(name, self.algorithm, host or DEFAULT_HOST, int(port or DEFAULT_PORT))
            self.client.receiver_callback = lambda s, m: self.events.put(("msg", s, m))
            self.client.file_callback = lambda s, p: self.events.put(("file", s, p))
            self.client.cipher_callback = lambda d, p, c: self.events.put(("cipher", d, p, c))
            self.client.error_callback = lambda t: self.events.put(("error", t))
            self.client.peers_callback = lambda: self.events.put(("peers",))
            self.client.connect()
        except Exception as e:
            self.client = None
            self.login_error.configure(text=f"Could not connect: {e}")
            return
        self.login_error.configure(text="")
        self.login.place_forget()
        self.name_label.configure(text=name)
        self.status_label.configure(text="● online", fg=T.GREEN)
        self._draw_avatar(name[:1], AVATAR_COLORS[sum(map(ord, name)) % len(AVATAR_COLORS)])
        self.messages.add("in", "Connected to the secure chat server.", kind="system")
        self._set_chat_enabled(True)
        self._refresh_peers()
        self.input.entry.focus_set()

    def on_algorithm(self, value):
        self.algorithm = value
        if self.client:
            self.client.set_algorithm(value)
            self._flash_status(f"Now using {ALGORITHM_LABELS[value]}")
        self._refresh_badge()

    def _toggle_cipher(self):
        self.show_cipher = not self.show_cipher
        on = self.show_cipher
        self.cipher_chip.restyle(bg=T.GREEN_BG if on else T.SURFACE2, fg=T.GREEN_TX if on else "#c7d3df",
                                 outline=T.GREEN_LINE if on else T.BORDER)
        self.messages.set_show_cipher(on)

    def _refresh_peers(self):
        peers = self.client.online_peers() if self.client else []
        self.to_box.configure(values=peers)
        if peers and self.to_var.get() not in peers:
            self.to_var.set(peers[0])
        elif not peers:
            self.to_var.set("")

    def _encryption_note(self, to):
        if self.algorithm == "ElGamal":
            return f"Encrypted with {to}'s public key (ElGamal)"
        return "Encrypted with the shared key (DES-CBC)"

    def _decryption_note(self):
        if self.client and self.client.last_incoming_algorithm == "DES":
            return "Decrypted with the shared key (DES-CBC)"
        return "Decrypted with your private key (ElGamal)"

    def send_text(self, text=None):
        if not self.client:
            return
        text = (text if text is not None else self.input.get()).strip()
        to = self.to_var.get()
        if not text:
            return
        if not to:
            self._flash_status("No one else is online yet.", T.RED)
            return
        try:
            cipher = self.client.send_message(to, text)
        except Exception as e:
            self._flash_status(str(e), T.RED)
            return
        self.messages.add("out", text, cipher=cipher)
        self._flash_status(self._encryption_note(to))
        self.input.clear()

    def attach(self, path=None):
        if not self.client:
            return
        to = self.to_var.get()
        if not to:
            self._flash_status("No one else is online yet.", T.RED)
            return
        path = path or filedialog.askopenfilename(title="Choose an image", filetypes=IMAGE_TYPES)
        if not path:
            return
        try:
            cipher = self.client.send_image(to, path)
        except Exception as e:
            self._flash_status(str(e), T.RED)
            return
        self.messages.add("out", path=path, cipher=cipher)
        self._flash_status(self._encryption_note(to))

    # ------------------------------------------------------------ event loop
    def _poll(self):
        try:
            while True:
                self._handle(self.events.get_nowait())
        except queue.Empty:
            pass
        self._poll_job = self.root.after(50, self._poll)

    def _handle(self, event):
        kind = event[0]
        if kind == "cipher":
            if event[1] == "in":
                self._last_in_cipher = event[3]
        elif kind == "msg":
            self.messages.add("in", event[2], cipher=self._last_in_cipher)
            self._flash_status(self._decryption_note())
        elif kind == "file":
            self.messages.add("in", text=event[2], path=event[2], cipher=self._last_in_cipher)
            self._flash_status(f"Image {self._decryption_note().lower()} and verified (SHA-256)")
        elif kind == "error":
            self._flash_status(event[1], T.RED)
        elif kind == "peers":
            self._refresh_peers()

    def run(self):
        self.root.mainloop()

    def shutdown(self):
        """Cancel timers and disconnect; safe to call more than once."""
        for job in (self._poll_job, self._status_job):
            if job:
                try:
                    self.root.after_cancel(job)
                except tk.TclError:
                    pass
        self._poll_job = self._status_job = None
        if self.client:
            self.client.disconnect()

    def on_close(self):
        self.shutdown()
        self.root.destroy()


if __name__ == "__main__":
    ChatGUI().run()
