# Wire protocol

Transport: TCP. Every message is **one JSON object on one line**, terminated by `\n`, encoded as UTF-8 (see `common/utils.py: JsonChannel`). A single line may not exceed 16 MB (`MAX_MESSAGE_BYTES`); longer lines make the server drop the connection.

Big integers (ElGamal values) are sent as ordinary JSON numbers.

## Client → server

### `register` (must be the first message)

```json
{"type": "register", "name": "alice", "pubkey": {"p": 123, "g": 5, "y": 456}}
```

Rejected with an `error` (and the connection closed) if the name is empty/whitespace or already in use, or if `pubkey` is not a valid key in the shared ElGamal group.

### `message` — encrypted text

```json
{"type": "message", "to": "bob", "algorithm": "ElGamal",
 "encrypted": [[c1, c2], [c1, c2]], "original": "optional plaintext"}
```

| `algorithm` | `encrypted` format |
|---|---|
| `DES` | base64 of `iv (8 bytes) + DES-CBC ciphertext` (PKCS#7 padded, fresh random IV) |
| `ElGamal` | list of `[c1, c2]` integer pairs, one per ≤254-byte chunk, encrypted for the **recipient's** public key |

`original` is optional and is only logged by the server. `from` is ignored; the server sets it from the registered name.

### `file` — encrypted image

```json
{"type": "file", "to": "bob", "algorithm": "ElGamal",
 "filename": "photo.png", "mime": "image/png", "size": 48213,
 "sha256": "<hex digest of the plaintext image>",
 "encrypted": "<base64 of iv + DES-CBC ciphertext>",
 "key": [[c1, c2]]}
```

- `DES`: the image is encrypted with the pre-shared key; there is no `key` field.
- `ElGamal`: the image is encrypted with a random 8-byte one-time DES key, and `key` holds that session key encrypted for the recipient's ElGamal public key.
- Limits: 5 MB image, types PNG/JPEG/GIF/BMP/WebP (checked by magic bytes, not just extension).

## Server → client

| `type` | Fields | Meaning |
|---|---|---|
| `registered` | `name` | Registration accepted |
| `peer` | `name`, `pubkey` | A peer is online (sent for existing peers on join, and for new joiners) |
| `peer_left` | `name` | A peer disconnected |
| `message` | as sent, plus `from` | Relayed text message |
| `file` | as sent, plus `from` | Relayed image |
| `error` | `message` | e.g. `"bob is not connected"`, `"name 'alice' is already taken"` |

## Receiver behaviour

- Text is decrypted according to the message's `algorithm`.
- Images are decrypted, checked against `sha256`, re-validated as an image, then saved to `received_files/` using a sanitised name with the extension of the *detected* type; existing files are never overwritten (`name_1.png`, `name_2.png`, …).
- A malformed or undecryptable item is reported through `error_callback` and does not stop the listener.

## ElGamal block format

All users share one fixed 2048-bit safe-prime group (`crypto/elgamal_group.py`, `g = 2`); `register` public keys must use exactly this `p` and `g` or they are rejected. Plaintext bytes are split into chunks of `(bits(p) - 1) // 8 - 1 = 254` bytes. Each chunk is prefixed with `0x01` before being read as an integer `m < p`, so leading zero bytes are preserved. For each chunk: pick a random `k` in `[1, q-1]` (`q = (p-1)/2`), output `c1 = g^k mod p`, `c2 = m · y^k mod p`. Decryption computes `m = c2 · (c1^x)^-1 mod p`, checks the `0x01` prefix, and strips it.
