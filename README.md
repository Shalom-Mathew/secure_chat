# 🔐 Secure Chat

A small client/server chat application that encrypts messages and images with **DES** or **ElGamal**, built for a cryptography course. A Tkinter GUI talks to a threaded relay server over plain TCP sockets.

> **Educational project.** DES is obsolete, the demo DES key is public, and the server can log plaintext by design (see [Security notes](#security-notes)). Do not use this to protect real secrets.

## Features

- **Two ciphers, selectable per client**
  - **DES-CBC** (pre-shared key, fresh random IV per message) for text and images.
  - **ElGamal** over a standard 2048-bit safe-prime group, chunked so messages of any length work. Every user gets a keypair instantly, and public keys are exchanged automatically through the server and validated before use.
- **Mixed algorithms** — an ElGamal user and a DES user can talk to each other; the receiver decrypts according to the algorithm named in each message.
- **Encrypted image sharing** — send PNG, JPEG, GIF, BMP or WebP files up to 5 MB.
  - ElGamal uses *hybrid encryption*: the image is encrypted with a random one-time DES key, and only that key is encrypted with the recipient's ElGamal public key.
  - Receiver verifies a SHA-256 checksum, re-checks the file is really an image, sanitises the filename, and never overwrites existing files. Images are saved to `received_files/`.
- **Modern dark GUI** — rounded chat bubbles, live **DES / ElGamal switch**, recipient picker fed by the live peer list, a **Ciphertext** toggle that shows what actually travelled over the wire under each message, image **Attach** with an inline preview, status hints ("Encrypted with Bob's public key"), and inline form errors.
- **Live peer directory** — the server announces who is online and their public keys.
- **Robust transport** — newline-delimited JSON framing (no merged/split messages), 16 MB per-message cap, duplicate-name and empty-name rejection, clean disconnect handling.
- **Test suite** — 48 tests (about 8 seconds), including end-to-end runs against a real server and two real GUI windows for each algorithm.

## Project layout

```
secure_chat/
├── client/
│   ├── client.py        # ChatClient: connect, key exchange, send/receive, decrypt
│   ├── file_share.py    # image validation, packing/unpacking, safe saving
│   ├── gui.py           # Tkinter front end (dark theme)
│   ├── theme.py         # design tokens: colours, spacing, radii, fonts
│   └── widgets.py       # rounded buttons, segmented control, pill entry, message list
├── server/
│   └── server.py        # ChatServer: registration, peer directory, message/file relay
├── crypto/
│   ├── des_crypto.py    # DESCipher (CBC, random IV; text and bytes)
│   ├── elgamal_crypto.py# ElGamalCipher (chunked, bytes + text, key validation)
│   └── elgamal_group.py # fixed 2048-bit safe prime shared by all users
├── common/
│   └── utils.py         # constants, DES key lookup, JsonChannel (line-framed JSON)
├── docs/
│   ├── PROTOCOL.md      # wire protocol reference
│   └── images/          # real screenshots of the app (DES and ElGamal)
├── tests/               # unittest suite (crypto, chat, file sharing)
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.9+ (developed on 3.11/3.12) with Tkinter (bundled with the standard Windows/macOS installers; on Debian/Ubuntu: `sudo apt install python3-tk`)
- [`pycryptodome`](https://pypi.org/project/pycryptodome/) for the ciphers and [`Pillow`](https://pypi.org/project/pillow/) for image previews (see `requirements.txt`). Without Pillow, PNG/GIF previews still work; other formats show a placeholder.

## Setup

```bash
git clone https://github.com/Shalom-Mathew/secure_chat.git
cd secure_chat
python -m venv venv
# Windows: venv\Scripts\activate      macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
```

## Running

Run everything from the project root (the commands use `python -m`).

**1. Start the server**

```bash
python -m server.server                 # localhost:5000
python -m server.server --host 0.0.0.0 --port 6000
python -m server.server --hide-plaintext   # do not log the 'original' field
```

**2. Start one GUI per user** (open a second terminal for each)

```bash
python -m client.gui
```

In each window choose **DES** or **ElGamal** with the switch at the top, enter a name, confirm the *Server* (`host:port`) and press **Connect**. Then pick who to talk to from the drop-down (it lists everyone online) and:

- write a message and press **Send** (or Enter), or
- press **Attach** and choose a picture.

You can flip the algorithm at any time; the next message uses the new one, and the receiver decrypts according to what the message says it used. **Ciphertext** shows or hides the encrypted form under each message. Received images are saved under `received_files/` and previewed inline.

### What it looks like

The same conversation with each algorithm. Under every bubble, `sent:` / `received:` shows the ciphertext that crossed the network; it is identical on both ends, and it is not the plaintext.

**DES** (shared key, CBC)

| Alice | Bob |
|---|---|
| ![Alice, DES](docs/images/app-des-alice.png) | ![Bob, DES](docs/images/app-des-bob.png) |

**ElGamal** (recipient's public key)

| Alice | Bob |
|---|---|
| ![Alice, ElGamal](docs/images/app-elgamal-alice.png) | ![Bob, ElGamal](docs/images/app-elgamal-bob.png) |

### Design notes

The look is defined once in `client/theme.py`: dark surfaces that get lighter with elevation, an 8-px spacing rhythm, one accent per meaning (blue = you, green = secure, amber = ciphertext, red = error), a consistent corner radius, and interaction feedback (hover, pressed, focus ring, disabled) within about 150 ms. Text inputs scroll their content, so long messages never spill outside the box.

> DES users must share the same key. The default demo key is `secret12`; set your own on **every** client with the `SECURE_CHAT_DES_KEY` environment variable (first 8 bytes are used).

### Using the client from Python

```python
from client.client import ChatClient

bob = ChatClient("bob", "ElGamal")
bob.receiver_callback = lambda sender, text: print(f"{sender}: {text}")
bob.file_callback = lambda sender, path: print(f"{sender} sent {path}")
bob.connect()

alice = ChatClient("alice", "ElGamal")
alice.connect()
alice.wait_for_peer("bob")
alice.send_message("bob", "hello")
alice.send_image("bob", "photo.png")
```

## Testing

```bash
python -m unittest discover -s tests -t . -v
```

GUI tests open real windows and are skipped automatically on machines without a display. The suite covers cipher round-trips (Unicode, empty and long inputs, wrong-key behaviour), message framing under load, mixed algorithms, error paths (duplicate names, offline recipients), encrypted image transfer with tamper, traversal and overwrite checks, and full GUI flows (text both ways, image with preview, live algorithm switching, input overflow, inline errors) for both DES and ElGamal. It runs in a few seconds because ElGamal keys use a shared precomputed group.

## How it works

1. A client connects and sends `register` with its name and ElGamal public key `{p, g, y}`.
2. The server replies `registered`, sends the new client every existing peer's key, and announces the new client to everyone else.
3. **DES:** the sender encrypts with the shared key and sends base64 ciphertext.
   **ElGamal:** the sender encrypts with the *recipient's* public key; only the recipient's private key can decrypt.
4. The server relays the message to the recipient (or returns an error to the sender if they are offline).

Full message formats are in [docs/PROTOCOL.md](docs/PROTOCOL.md).

## Security notes

This project demonstrates the algorithms; it is intentionally not a hardened system.

- **The server sees plaintext text messages.** Clients attach an `original` field that the server prints next to the ciphertext, which is what the demo log shows. Construct clients with `send_plaintext=False` (and/or run the server with `--hide-plaintext`) to stop sending/logging it. Images are never sent or logged in plaintext.
- **DES** has a 56-bit key and is broken by brute force. The default key is public. Both text and images use DES-CBC with a random IV per message, but the key is still only 56 bits.
- **ElGamal uses a 2048-bit safe prime**, and peers' public keys are rejected unless they use that group. It is textbook ElGamal (no padding scheme or authentication), so ciphertexts are malleable.
- No authentication: anyone can register any free name, and the server could substitute public keys (no key verification/fingerprints).
- No transport encryption (TLS) and no forward secrecy.

## License

No license has been specified yet; add one before reusing this code.
