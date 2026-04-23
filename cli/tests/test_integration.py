import asyncio
import base64
import ssl

import aiohttp
import pytest

from terminalsync.crypto import (
    decrypt_frame,
    derive_session_key,
    encrypt_frame,
    generate_keypair,
    generate_psk,
)
from terminalsync.pairing import make_label, make_sid
from terminalsync.protocol import (
    InputMsg,
    OutputMsg,
    PingMsg,
    PongMsg,
    ReplayMsg,
    decode,
    encode,
)
from terminalsync.pty_proxy import PtyProxy
from terminalsync.server import SessionHandler, build_app, start_server
from terminalsync.session import Session
from terminalsync.status import StatusLine
from terminalsync.tls import generate_ephemeral_tls


async def _make_test_server():
    """Spin up a terminalsync server running a simple shell command."""
    privkey, pubkey = generate_keypair()
    psk = generate_psk()
    sid = make_sid()
    label = "test — integration"

    ssl_ctx, cert_der = generate_ephemeral_tls("127.0.0.1")
    proxy = PtyProxy(["bash", "-c", "echo hello_integration; sleep 60"], mirror_local=False)
    session = Session(sid=sid, label=label, pubkey=pubkey, privkey=privkey, psk=psk)
    status = StatusLine()

    app = build_app(session, proxy, status)
    runner, port = await start_server(app, ssl_ctx, "127.0.0.1", 0)

    proxy_task = asyncio.create_task(proxy.start())
    # Give the shell a moment to produce output
    await asyncio.sleep(0.3)

    return runner, proxy, session, port, proxy_task


async def _headless_pair(port: int, server_session: Session):
    """Connect as phone: perform handshake, return (ws, session_key, client)."""
    phone_priv, phone_pub = generate_keypair()

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    connector = aiohttp.TCPConnector(ssl=ssl_ctx)
    client = aiohttp.ClientSession(connector=connector)

    ws = await client.ws_connect(
        f"wss://127.0.0.1:{port}/s/{server_session.sid}",
        timeout=aiohttp.ClientTimeout(total=5),
    )

    # Send phone pubkey (unencrypted, first frame)
    await ws.send_str(base64.urlsafe_b64encode(phone_pub).decode())

    # Derive session key — same derivation as server
    session_key = derive_session_key(phone_priv, server_session.pubkey, server_session.psk)

    return ws, session_key, client


async def _collect_output(ws, session_key: bytes, timeout: float = 3.0) -> bytes:
    """Collect OutputMsg data until timeout."""
    received = b""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        remaining = deadline - asyncio.get_event_loop().time()
        try:
            msg = await asyncio.wait_for(ws.receive(), timeout=min(remaining, 0.5))
            if msg.type == aiohttp.WSMsgType.BINARY:
                plain = decrypt_frame(session_key, msg.data)
                decoded = decode(plain)
                if isinstance(decoded, OutputMsg):
                    received += decoded.data
        except asyncio.TimeoutError:
            break
    return received


@pytest.mark.asyncio
async def test_handshake_and_output():
    runner, proxy, session, port, proxy_task = await _make_test_server()
    try:
        ws, session_key, client = await _headless_pair(port, session)

        replay = encode(ReplayMsg(from_seq=0))
        await ws.send_bytes(encrypt_frame(session_key, replay))

        received = await _collect_output(ws, session_key, timeout=3)
        assert b"hello_integration" in received

        await ws.close()
        await client.close()
    finally:
        proxy.terminate()
        proxy_task.cancel()
        await runner.cleanup()
        session.wipe_keys()


@pytest.mark.asyncio
async def test_input_reaches_pty():
    runner, proxy, session, port, proxy_task = await _make_test_server()
    try:
        ws, session_key, client = await _headless_pair(port, session)

        # Send some input
        input_msg = encode(InputMsg(data=b"echo from_phone\n"))
        await ws.send_bytes(encrypt_frame(session_key, input_msg))

        received = await _collect_output(ws, session_key, timeout=3)
        assert b"from_phone" in received

        await ws.close()
        await client.close()
    finally:
        proxy.terminate()
        proxy_task.cancel()
        await runner.cleanup()
        session.wipe_keys()


@pytest.mark.asyncio
async def test_ping_pong():
    runner, proxy, session, port, proxy_task = await _make_test_server()
    try:
        ws, session_key, client = await _headless_pair(port, session)

        ping = encode(PingMsg(seq=99))
        await ws.send_bytes(encrypt_frame(session_key, ping))

        pong_received = False
        deadline = asyncio.get_event_loop().time() + 3
        while asyncio.get_event_loop().time() < deadline:
            remaining = deadline - asyncio.get_event_loop().time()
            try:
                msg = await asyncio.wait_for(ws.receive(), timeout=min(remaining, 0.5))
                if msg.type == aiohttp.WSMsgType.BINARY:
                    plain = decrypt_frame(session_key, msg.data)
                    decoded = decode(plain)
                    if isinstance(decoded, PongMsg) and decoded.seq == 99:
                        pong_received = True
                        break
            except asyncio.TimeoutError:
                break

        assert pong_received

        await ws.close()
        await client.close()
    finally:
        proxy.terminate()
        proxy_task.cancel()
        await runner.cleanup()
        session.wipe_keys()


@pytest.mark.asyncio
async def test_wrong_session_id_rejected():
    runner, proxy, session, port, proxy_task = await _make_test_server()
    try:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        client = aiohttp.ClientSession(connector=connector)

        # Connecting with wrong sid should fail with a non-101 response
        try:
            ws = await client.ws_connect(
                f"wss://127.0.0.1:{port}/s/wrongid",
                timeout=aiohttp.ClientTimeout(total=5),
            )
            # If it somehow connected, close it
            await ws.close()
            rejected = False
        except Exception:
            rejected = True

        assert rejected, "Server should reject wrong session ID"
        await client.close()
    finally:
        proxy.terminate()
        proxy_task.cancel()
        await runner.cleanup()
        session.wipe_keys()
