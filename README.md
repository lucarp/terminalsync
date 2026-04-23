# TerminalSync

**Mirror a terminal to your phone — E2E encrypted, peer-to-peer, no daemon.**

Run `terminalsync` in any terminal tab. Scan the QR code with your phone. See your terminal, live. Close the tab, and everything shuts down — no background process, no cloud relay, no stored keys.

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
pipx install terminalsync
```

Or from source:

```bash
git clone https://github.com/webmaster@clippingcacd.com.br/terminalsync  # replace with your username
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

Environment variable `TERMINALSYNC_HOST` overrides `--host`. Useful for Tailscale:

```bash
export TERMINALSYNC_HOST=100.x.y.z   # your Tailscale IP
terminalsync
```

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

## Network

- **Same Wi-Fi (LAN):** Works out of the box.
- **Remote (recommended):** [Tailscale](https://tailscale.com) — set `TERMINALSYNC_HOST` to your tailnet IP.
- **Remote (manual):** Port-forward your router or use a tunnel (ngrok, cloudflared). A warning is displayed for public IPs.

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

Issues and PRs welcome. See the [architecture document](docs/superpowers/plans/2026-04-23-terminalsync-mvp.md) for design decisions.

## License

MIT — see [LICENSE](LICENSE).
