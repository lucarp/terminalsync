# TerminalSync — Architecture

## Overview

TerminalSync is a single-process terminal mirror. Running `terminalsync` in a terminal tab starts everything; closing the tab stops everything. There are no background daemons, no stored keys, no cloud services.

The primary use case is monitoring long-running processes (AI agents, builds, servers) from a phone without needing SSH access or tmux.

---

## Process model

```
┌─────────────────────────────────────────────────────┐
│  terminalsync process                               │
│                                                     │
│  ┌──────────┐   PTY    ┌───────────────────────┐   │
│  │  Shell   │◄────────►│  PtyProxy             │   │
│  │  (bash)  │          │  - scrollback buffer  │   │
│  └──────────┘          │  - output callbacks   │   │
│                        └──────────┬────────────┘   │
│                                   │                 │
│                        ┌──────────▼────────────┐   │
│                        │  aiohttp server        │   │
│                        │  HTTP + WebSocket      │   │
│                        └──────────┬────────────┘   │
└───────────────────────────────────┼────────────────┘
                                    │ WSS (or WS via tunnel)
                              ┌─────▼──────┐
                              │   Phone    │
                              │  browser   │
                              └────────────┘
```

The PTY proxy forks the shell into a pseudo-terminal, reads its output, and fans it out to: the local terminal (mirrored) and any registered WebSocket callbacks.

---

## Cryptographic protocol

### Key exchange

Both sides generate ephemeral X25519 keypairs. The server's public key and a pre-shared key (PSK) are embedded in the QR code pairing payload. The phone generates its own keypair on load.

```
server_priv, server_pub  ←  generated at startup, embedded in QR
phone_priv, phone_pub    ←  generated in browser on page load

DH_secret = X25519(server_priv, phone_pub)
           = X25519(phone_priv, server_pub)   # same value

session_key = HKDF-SHA256(
    ikm  = DH_secret ‖ PSK,
    salt = 32 zero bytes,
    info = b"terminalsync-v2-session-key",
    len  = 32
)
```

The PSK is a random 32-byte value, also embedded in the QR. It prevents a passive attacker who observed the QR code from impersonating the server.

### Handshake

```
Phone → Server:  base64url(phone_pub)          [plaintext, over WSS]
Server → Phone:  [derives session_key, silent]
Phone → Server:  encrypt(HelloMsg)             [all subsequent frames encrypted]
```

### Frame encryption

Every WebSocket message (both directions) is authenticated and encrypted:

```
frame = nonce (24 bytes) ‖ XSalsa20-Poly1305(session_key, nonce, plaintext)
```

A corrupted or replayed frame is silently dropped.

### Short Authentication String (SAS)

To detect MITM, both sides display a 12-digit code derived from the session key:

```
digest = SHA-256(b"terminalsync-sas-v2" ‖ session_key)
SAS    = "%03d-%03d-%03d-%03d" % (
    digest[0:4]  % 1000,
    digest[4:8]  % 1000,
    digest[8:12] % 1000,
    digest[12:16] % 1000,
)
```

The user visually compares the code on both screens to confirm no MITM.

### TLS

The server generates a per-invocation self-signed P-256 certificate. Its DER fingerprint (first 16 hex chars of SHA-256) is embedded in the QR payload so the browser can pin it. The certificate expires after 24 hours.

When `--public-url` is set (ngrok, cloudflared, SSH tunnel), the server binds plain HTTP locally and the tunnel provides TLS. The cert fingerprint field is still included in the payload for forward compatibility.

---

## Wire protocol

All messages are CBOR-encoded maps with a string `"t"` field as the type discriminator, then encrypted as described above.

| Type | Direction | Fields | Description |
|------|-----------|--------|-------------|
| `hello` | Phone→Server | `device`, `label`, `caps` | First encrypted message after key exchange |
| `output` | Server→Phone | `seq`, `data` | Terminal output chunk |
| `input` | Phone→Server | `data` | Keystrokes from phone |
| `resize` | Phone→Server | `cols`, `rows` | Terminal resize |
| `ping` | Phone→Server | `seq` | Keepalive |
| `pong` | Server→Phone | `seq` | Keepalive reply |
| `replay` | Phone→Server | `from_seq` | Request scrollback from seq |
| `signal` | Phone→Server | `sig` | Send Unix signal to child (e.g. `SIGINT`) |
| `bye` | Either | — | Graceful close |

Sequence numbers in `output` are monotonically increasing integers. `replay` uses them to request catch-up on reconnect — the server keeps the last ~1 MB of scrollback in a deque.

---

## QR pairing payload

The QR code encodes a URL of the form:

```
https://HOST:PORT/?pair=BASE64URL(JSON)
```

The JSON payload:

```json
{
  "v": 2,
  "sid": "<hex session ID>",
  "label": "<hostname — cwd>",
  "endpoint": "wss://HOST:PORT/s/SID",
  "pub": "<base64url server public key>",
  "psk": "<base64url pre-shared key>",
  "fpr": "<first 16 hex chars of SHA-256(cert DER)>"
}
```

`endpoint` uses `ws://` instead of `wss://` when the server is bound as plain HTTP (tunnel mode).

---

## Tunnel mode (`--public-url`)

When running behind a reverse tunnel (ngrok, cloudflared, SSH `-R`):

- The server binds plain HTTP locally — the tunnel provides TLS externally.
- `adv_host` / `adv_port` are derived from the `--public-url` argument instead of the bind address.
- The endpoint scheme is `ws://` for `http://` public URLs, `wss://` for `https://`.

This means `ngrok http 12345` (no flags) works without any TLS verification workaround.

---

## Security properties and non-properties

**Provided:**
- Confidentiality and integrity of all terminal data (XSalsa20-Poly1305)
- Forward secrecy — session keys are ephemeral and zeroed on exit
- MITM detection — SAS code shown on both screens
- No persistent attack surface — no open ports when not actively sharing

**Not provided:**
- TLS cert pinning in the browser (fpr field is not yet verified by the web client — planned)
- Protection against QR code interception (attacker who photographs the QR gets the PSK and public key)
- Multi-viewer sessions (only one phone session at a time)

---

## Design constraints (non-negotiable)

- **No daemon.** The process lives and dies with the terminal tab. `isatty()` and `getppid() != 1` are checked at startup.
- **No disk keys.** All key material lives in process memory and is zeroed in the `finally` block on exit.
- **No cloud relay.** The phone connects directly to the machine (or via a user-controlled tunnel).
