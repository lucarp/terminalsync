import asyncio
import os
import signal
import socket
import sys
from urllib.parse import urlparse

import click

from .crypto import generate_keypair, generate_psk
from .pairing import build_payload, make_label, make_sid, payload_to_url, render_qr_terminal
from .pty_proxy import PtyProxy
from .server import build_app, start_server
from .session import Session
from .status import StatusLine
from .tls import generate_ephemeral_tls
from .tty_guard import assert_interactive_terminal


def _get_default_ip() -> str:
    """Return the primary outbound IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


@click.command()
@click.option(
    "--host", default=None, envvar="TERMINALSYNC_HOST",
    help="IP/hostname to advertise in QR (default: auto-detect)",
)
@click.option(
    "--port", default=0, type=int,
    help="Port to listen on (default: random ephemeral)",
)
@click.option(
    "--command", default=None,
    help="Command to run inside PTY (default: $SHELL)",
)
@click.option(
    "--public-url", default=None, envvar="TERMINALSYNC_PUBLIC_URL",
    help="Public URL for QR code (e.g. ngrok/cloudflared URL). Overrides --host/--port in QR.",
)
@click.version_option()
def main(host: str | None, port: int, command: str | None, public_url: str | None) -> None:
    """Mirror a terminal to your phone — E2E encrypted, no daemon."""
    assert_interactive_terminal()

    cmd = command.split() if command else [os.environ.get("SHELL", "/bin/bash")]
    bind_host = host or _get_default_ip()

    asyncio.run(_run(bind_host, port, cmd, public_url))


async def _run(host: str, port: int, cmd: list[str], public_url: str | None = None) -> None:
    status = StatusLine()

    privkey, pubkey = generate_keypair()
    psk = generate_psk()
    sid = make_sid()
    label = make_label()

    ssl_ctx, cert_der = generate_ephemeral_tls(host)

    proxy = PtyProxy(cmd, mirror_local=True)
    session = Session(sid=sid, label=label, pubkey=pubkey, privkey=privkey, psk=psk)

    app = build_app(session, proxy, status)
    # When behind a tunnel, the tunnel provides TLS — bind plain HTTP locally.
    effective_ssl = None if public_url else ssl_ctx
    runner, actual_port = await start_server(app, effective_ssl, "0.0.0.0", port)

    # Advertised host/port may differ from bind address when behind a tunnel (ngrok, cloudflared).
    if public_url:
        parsed = urlparse(public_url)
        adv_host = parsed.hostname or host
        adv_port = parsed.port or (443 if parsed.scheme in ("https", "wss") else 80)
    else:
        adv_host = host
        adv_port = actual_port

    payload = build_payload(sid, label, adv_host, adv_port, pubkey, psk, cert_der)
    url = payload_to_url(payload)
    qr_str = render_qr_terminal(url)

    status.print_pair_info(qr_str, url)
    status.update("Waiting for phone to pair... | Ctrl-C to exit")

    loop = asyncio.get_event_loop()

    def on_signal() -> None:
        proxy.terminate()

    for sig in (signal.SIGHUP, signal.SIGTERM):
        loop.add_signal_handler(sig, on_signal)

    try:
        await proxy.start()
    except KeyboardInterrupt:
        pass
    finally:
        await runner.cleanup()
        session.wipe_keys()
        status.clear()
        sys.stdout.write("\n")
