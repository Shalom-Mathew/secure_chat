"""Tkinter front end.  Run with:  python -m client.gui"""

import queue
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from client.client import ALGORITHMS, ChatClient
from common.utils import DEFAULT_HOST, DEFAULT_PORT


class ChatGUI:
    def __init__(self):
        self.client = None
        self.incoming = queue.Queue()  # network threads -> Tk main thread
        self.root = tk.Tk()
        self.root.title("🔐 Secure Chat Application")
        self.setup_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self.poll_incoming)

    def run(self):
        self.root.mainloop()

    def setup_widgets(self):
        top_frame = tk.Frame(self.root)
        top_frame.pack(padx=10, pady=10)

        tk.Label(top_frame, text="Your Name:").grid(row=0, column=0)
        self.name_entry = tk.Entry(top_frame)
        self.name_entry.grid(row=0, column=1)

        tk.Label(top_frame, text="Recipient:").grid(row=1, column=0)
        self.recipient_entry = tk.Entry(top_frame)
        self.recipient_entry.grid(row=1, column=1)

        tk.Label(top_frame, text="Algorithm:").grid(row=2, column=0)
        self.algo_choice = ttk.Combobox(top_frame, values=list(ALGORITHMS), state="readonly")
        self.algo_choice.grid(row=2, column=1)
        self.algo_choice.current(0)

        tk.Label(top_frame, text="Server:").grid(row=3, column=0)
        self.server_entry = tk.Entry(top_frame)
        self.server_entry.insert(0, f"{DEFAULT_HOST}:{DEFAULT_PORT}")
        self.server_entry.grid(row=3, column=1)

        self.connect_button = tk.Button(top_frame, text="Connect", command=self.connect_to_server)
        self.connect_button.grid(row=4, column=0, columnspan=2, pady=5)

        self.chat_area = scrolledtext.ScrolledText(self.root, width=60, height=20, state="disabled")
        self.chat_area.pack(padx=10, pady=10)

        msg_frame = tk.Frame(self.root)
        msg_frame.pack(padx=10, pady=5)
        self.msg_entry = tk.Entry(msg_frame, width=40)
        self.msg_entry.grid(row=0, column=0, padx=5)
        self.msg_entry.bind("<Return>", lambda _e: self.send_message())
        self.send_button = tk.Button(msg_frame, text="Send", command=self.send_message, state="disabled")
        self.send_button.grid(row=0, column=1)
        self.image_button = tk.Button(msg_frame, text="Send Image", command=self.send_image, state="disabled")
        self.image_button.grid(row=0, column=2, padx=5)

    def connect_to_server(self):
        name = self.name_entry.get().strip()
        algo = self.algo_choice.get().strip()
        if not name:
            messagebox.showerror("Error", "Name cannot be empty")
            return
        host, _, port = self.server_entry.get().strip().partition(":")
        try:
            self.client = ChatClient(name=name, algorithm=algo, server_host=host or DEFAULT_HOST,
                                     server_port=int(port or DEFAULT_PORT))
            self.client.receiver_callback = lambda s, m: self.incoming.put(f"{s} → You: {m}")
            self.client.error_callback = lambda t: self.incoming.put(f"⚠️ {t}")
            self.client.file_callback = lambda s, path: self.incoming.put(f"🖼️ {s} sent an image → saved to {path}")
            self.client.connect()
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))
            return
        self.append_chat("✅ Connected to the secure chat server.")
        self.connect_button.config(state="disabled")
        self.send_button.config(state="normal")
        self.image_button.config(state="normal")

    def send_message(self):
        if not self.client:
            return
        to = self.recipient_entry.get().strip()
        msg = self.msg_entry.get().strip()
        if not to or not msg:
            return
        try:
            self.client.send_message(to, msg)
        except Exception as e:
            self.append_chat(f"⚠️ {e}")
            return
        self.append_chat(f"You → {to}: {msg}")
        self.msg_entry.delete(0, tk.END)

    def send_image(self):
        to = self.recipient_entry.get().strip()
        if not self.client or not to:
            return
        path = filedialog.askopenfilename(title="Choose an image",
                                          filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp *.webp")])
        if not path:
            return
        try:
            self.client.send_image(to, path)
        except Exception as e:
            self.append_chat(f"⚠️ {e}")
            return
        self.append_chat(f"You → {to}: 🖼️ {path.replace(chr(92), '/').rsplit('/', 1)[-1]}")

    def poll_incoming(self):
        try:
            while True:
                self.append_chat(self.incoming.get_nowait())
        except queue.Empty:
            pass
        self.root.after(100, self.poll_incoming)

    def append_chat(self, msg):
        self.chat_area.config(state="normal")
        self.chat_area.insert(tk.END, msg + "\n")
        self.chat_area.config(state="disabled")
        self.chat_area.see(tk.END)

    def on_close(self):
        if self.client:
            self.client.disconnect()
        self.root.destroy()


if __name__ == "__main__":
    ChatGUI().run()
