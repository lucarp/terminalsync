# TerminalSync

**Mirror a terminal to your phone — E2E encrypted, peer-to-peer, no daemon.**

Run `terminalsync` in any terminal tab. Scan the QR code with your phone. See your terminal, live, in your browser. Close the tab and everything shuts down — no background process, no cloud relay, no stored keys.

Built for leaving AI coding agents (Claude Code, etc.) running at home while staying able to observe and intervene from anywhere.

## How it works

1. `terminalsync` allocates a PTY, runs your shell, and starts a WebSocket server on an ephemeral port.
2. A QR code is printed in the terminal encoding the endpoint and cryptographic pairing data.
3. Scan it with your phone's browser. A full X25519 key exchange happens — both sides derive a shared key that never leaves their devices.
4. Your terminal is mirrored to the phone in real time, encrypted with XSalsa20-Poly1305.
5. When the terminal tab closes, the process exits, keys are zeroed, and the phone's session drops.

**Zero servers. Zero daemons. Zero persistent keys.**

## Install

```bash
pipx install git+https://github.com/lucarp/terminalsync.git#subdirectory=cli
```

Or from source:

```bash
git clone https://github.com/lucarp/terminalsync
cd terminalsync/cli
pip install -e .
```

## Usage

```bash
# In any terminal tab:
terminalsync

# Scan the QR code with your phone — open the printed URL in mobile Safari/Chrome
# Accept the self-signed certificate warning
# Your terminal appears in the browser
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | auto-detect LAN IP | IP/hostname to advertise in the QR code |
| `--port` | random ephemeral | Port to listen on |
| `--command` | `$SHELL` | Command to run inside the PTY |
| `--public-url` | — | Public URL for QR (ngrok, cloudflared, SSH tunnel). Overrides `--host`/`--port` in QR. |

Environment variable `TERMINALSYNC_HOST` overrides `--host`.

## Connecting from your phone

### Same Wi-Fi (LAN)

Works out of the box. `terminalsync` auto-detects your LAN IP and prints it in the QR code.

The first time you open the URL, your phone's browser will show a **self-signed certificate warning** — tap Advanced → Proceed to accept it. The WebSocket will connect on the same certificate.

### Tailscale (recommended for remote)

[Tailscale](https://tailscale.com) is free for personal use. Install it on your computer and phone, then:

```bash
terminalsync --host $(tailscale ip -4)
```

Your phone connects directly to your computer over the Tailscale network — no intermediate server, no extra setup.

### ngrok / cloudflared (remote, no VPN)

```bash
# Terminal 1 — expose local port via ngrok
ngrok http 12345

# Terminal 2 — start terminalsync pointing at the ngrok URL
terminalsync --port 12345 --public-url https://YOUR-SUBDOMAIN.ngrok-free.app
```

When `--public-url` is set, terminalsync binds plain HTTP locally and lets the tunnel handle TLS. The QR code encodes the tunnel URL so your phone connects through ngrok.

The same pattern works with cloudflared:

```bash
cloudflared tunnel --url http://localhost:12345
terminalsync --port 12345 --public-url https://YOUR-SUBDOMAIN.trycloudflare.com
```

### SSH tunnel (remote, own server)

If you have a VPS:

```bash
# Forward a port on the server back to your local machine
ssh -R 12345:localhost:12345 user@your-server.com

terminalsync --port 12345 --public-url http://your-server.com:12345
```

### Local browser testing (no phone)

```bash
terminalsync --port 12345 --public-url http://localhost:12345
```

Binds plain HTTP, no certificate warning — open the printed URL directly in your browser.

## Why not just SSH?

SSH opens a **new** session. terminalsync mirrors the session **already running** — the one with your AI agent mid-task, your build in progress, your REPL state intact. Without terminalsync you'd need `tmux` or `screen` to share a running process. terminalsync does it with a QR scan, no extra setup required.

You can also work on your computer and phone **simultaneously** — both see and interact with the same live terminal.

## Security

| Property | Implementation |
|----------|---------------|
| Key exchange | X25519 (Curve25519 ECDH) |
| Symmetric encryption | XSalsa20-Poly1305 via libsodium/PyNaCl |
| Key derivation | HKDF-SHA256 over (DH output ‖ PSK) |
| Transport | TLS with per-invocation self-signed cert |
| Cert trust | Fingerprint pinned in the QR code |
| Verification | 12-digit Short Authentication String (compare on both screens) |
| Key storage | Process memory only — zeroed on exit |
| Attack surface | No open port when not actively sharing |

TerminalSync refuses to run detached: it checks `isatty()` on stdin/stdout and rejects execution if its parent is PID 1. There is no daemon mode.

## Requirements

- Python 3.11+
- macOS or Linux
- Phone with a modern browser (Safari, Chrome)

## Roadmap

- [x] Phase 0: PTY + WebSocket validation
- [x] Phase 1: Full encryption, QR pairing, web client
- [ ] Phase 2: Native iOS/Android app (React Native, Keychain/Keystore vault, push notifications)
- [ ] Phase 3: Optional zero-knowledge relay for NAT traversal without Tailscale

## Contributing

Issues and PRs welcome. See [docs/architecture.md](docs/architecture.md) for design decisions and protocol details.

## License

MIT — see [LICENSE](LICENSE).
