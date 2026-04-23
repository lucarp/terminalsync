import io
import pytest
from terminalsync.status import StatusLine


def make_status():
    buf = io.StringIO()
    return StatusLine(stream=buf), buf


def test_update_writes_to_stream():
    s, buf = make_status()
    s.update("hello")
    assert "hello" in buf.getvalue()


def test_update_starts_with_carriage_return():
    s, buf = make_status()
    s.update("msg")
    assert buf.getvalue().startswith("\r")


def test_clear_erases_line():
    s, buf = make_status()
    s.update("something")
    s.clear()
    val = buf.getvalue()
    assert "\r" in val
    assert "\033[K" in val


def test_terminalsync_prefix():
    s, buf = make_status()
    s.update("Waiting...")
    assert "[TerminalSync]" in buf.getvalue()
