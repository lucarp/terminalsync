import asyncio
import pytest
from terminalsync.pty_proxy import PtyProxy


@pytest.mark.asyncio
async def test_proxy_captures_output():
    """PtyProxy runs a command and its output is delivered to callbacks."""
    received = []

    proxy = PtyProxy(["bash", "-c", "echo hello_pty; exit"], mirror_local=False)
    proxy.add_output_callback(lambda seq, data: received.append(data))

    await asyncio.wait_for(proxy.start(), timeout=5)

    combined = b"".join(received)
    assert b"hello_pty" in combined


@pytest.mark.asyncio
async def test_proxy_seq_increments():
    seqs = []

    proxy = PtyProxy(["bash", "-c", "printf 'a'; printf 'b'; exit"], mirror_local=False)
    proxy.add_output_callback(lambda seq, data: seqs.append(seq))

    await asyncio.wait_for(proxy.start(), timeout=5)

    assert len(seqs) >= 1
    assert seqs == sorted(seqs)  # monotonically increasing


@pytest.mark.asyncio
async def test_proxy_scrollback():
    proxy = PtyProxy(["bash", "-c", "echo scrollback_test; exit"], mirror_local=False)
    await asyncio.wait_for(proxy.start(), timeout=5)

    replay = proxy.get_scrollback_from(0)
    combined = b"".join(d for _, d in replay)
    assert b"scrollback_test" in combined


@pytest.mark.asyncio
async def test_proxy_last_seq():
    proxy = PtyProxy(["bash", "-c", "echo x; exit"], mirror_local=False)
    await asyncio.wait_for(proxy.start(), timeout=5)
    assert proxy.last_seq >= 1
