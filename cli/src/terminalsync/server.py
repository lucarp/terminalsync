import asyncio
import base64
import importlib.resources
import logging
import ssl
from typing import Optional

from aiohttp import web
import aiohttp

from .crypto import decrypt_frame, derive_session_key, encrypt_frame, generate_sas
from .protocol import (
    ByeMsg, HelloMsg, InputMsg, OutputMsg, PingMsg, PongMsg, ReplayMsg,
    ResizeMsg, SignalMsg, decode, encode,
)
from .pty_proxy import PtyProxy
from .session import Session
from .status import StatusLine

log = logging.getLogger(__name__)


class SessionHandler:
    def __init__(self, session: Session, proxy: PtyProxy, status: StatusLine) -> None:
        self._session = session
        self._proxy = proxy
        self._status = status
        self._ws: Optional[web.WebSocketResponse] = None

    async def handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._ws = ws

        try:
            # Handshake: receive phone's pubkey (first frame, unencrypted, base64url)
            first = await ws.receive()
            if first.type not in (aiohttp.WSMsgType.BINARY, aiohttp.WSMsgType.TEXT):
                await ws.close()
                return ws

            raw = first.data if isinstance(first.data, str) else first.data.decode()
            # Add padding back before decoding
            phone_pubkey = base64.urlsafe_b64decode(raw + "==")

            # Derive session key
            self._session.session_key = derive_session_key(
                self._session.privkey, phone_pubkey, self._session.psk
            )
            self._session.sas = generate_sas(self._session.session_key)

            self._status.update(
                f"Connected — auth code: \033[1m{self._session.sas}\033[0m | Ctrl-C to exit"
            )

            # Register PTY output → WS forwarder
            def on_output(seq: int, data: bytes) -> None:
                asyncio.create_task(self._send_output(seq, data))

            self._proxy.add_output_callback(on_output)

            try:
                await self._recv_loop(ws)
            finally:
                self._proxy.remove_output_callback(on_output)

        except Exception as exc:
            log.debug("WebSocket error: %s", exc)
        finally:
            self._ws = None
            self._status.update("Phone disconnected — waiting to reconnect | Ctrl-C to exit")

        return ws

    async def _send_output(self, seq: int, data: bytes) -> None:
        if self._ws and not self._ws.closed and self._session.session_key:
            try:
                frame = encode(OutputMsg(seq=seq, data=data))
                await self._ws.send_bytes(encrypt_frame(self._session.session_key, frame))
            except Exception:
                pass

    async def _recv_loop(self, ws: web.WebSocketResponse) -> None:
        async for msg in ws:
            if msg.type != aiohttp.WSMsgType.BINARY:
                continue
            if not self._session.session_key:
                continue
            try:
                plain = decrypt_frame(self._session.session_key, msg.data)
                decoded = decode(plain)
            except Exception:
                continue  # malformed or wrong key — ignore

            if isinstance(decoded, HelloMsg):
                self._session.device_name = decoded.device
                self._status.update(
                    f"Connected: {decoded.device} — auth: \033[1m{self._session.sas}\033[0m | Ctrl-C to exit"
                )
            elif isinstance(decoded, InputMsg):
                self._proxy.write_input(decoded.data)
            elif isinstance(decoded, ResizeMsg):
                self._proxy.resize(decoded.cols, decoded.rows)
            elif isinstance(decoded, PingMsg):
                reply = encode(PongMsg(seq=decoded.seq))
                await ws.send_bytes(encrypt_frame(self._session.session_key, reply))
            elif isinstance(decoded, ReplayMsg):
                for seq, data in self._proxy.get_scrollback_from(decoded.from_seq):
                    await self._send_output(seq, data)
            elif isinstance(decoded, SignalMsg):
                self._proxy.send_signal(decoded.sig)
            elif isinstance(decoded, ByeMsg):
                break


def build_app(session: Session, proxy: PtyProxy, status: StatusLine) -> web.Application:
    handler = SessionHandler(session, proxy, status)
    app = web.Application()

    async def serve_root(request: web.Request) -> web.Response:
        pkg = importlib.resources.files("terminalsync") / "web_client" / "index.html"
        html = pkg.read_text(encoding="utf-8")
        return web.Response(text=html, content_type="text/html")

    async def serve_static(request: web.Request) -> web.Response:
        filename = request.match_info["filename"]
        try:
            pkg = importlib.resources.files("terminalsync") / "web_client" / filename
            content = pkg.read_bytes()
        except (FileNotFoundError, TypeError):
            raise web.HTTPNotFound()
        ct = "application/javascript" if filename.endswith(".js") else "text/plain"
        return web.Response(body=content, content_type=ct)

    async def serve_ws(request: web.Request) -> web.WebSocketResponse:
        sid = request.match_info["sid"]
        if sid != session.sid:
            raise web.HTTPNotFound()
        return await handler.handle_ws(request)

    app.router.add_get("/", serve_root)
    app.router.add_get("/s/{sid}", serve_ws)
    app.router.add_get("/{filename}", serve_static)

    return app


async def start_server(
    app: web.Application,
    ssl_ctx: ssl.SSLContext,
    host: str,
    port: int,
) -> tuple[web.AppRunner, int]:
    """Start server and return (runner, actual_port)."""
    import socket as _socket

    # If port is 0, find a free port first (aiohttp doesn't expose the bound port easily)
    if port == 0:
        with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            port = s.getsockname()[1]

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port, ssl_context=ssl_ctx)
    await site.start()
    return runner, port
