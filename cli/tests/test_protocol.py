import pytest
from terminalsync.protocol import (
    encode, decode,
    OutputMsg, InputMsg, ResizeMsg, PingMsg, PongMsg,
    ReplayMsg, SignalMsg, ByeMsg, HelloMsg,
)


def roundtrip(msg):
    return decode(encode(msg))


def test_output_roundtrip():
    msg = OutputMsg(seq=42, data=b"\x1b[32mhello\x1b[0m")
    rt = roundtrip(msg)
    assert isinstance(rt, OutputMsg)
    assert rt.seq == 42
    assert rt.data == b"\x1b[32mhello\x1b[0m"


def test_input_roundtrip():
    msg = InputMsg(data=b"yes\n")
    rt = roundtrip(msg)
    assert isinstance(rt, InputMsg)
    assert rt.data == b"yes\n"


def test_resize_roundtrip():
    msg = ResizeMsg(cols=220, rows=50)
    rt = roundtrip(msg)
    assert isinstance(rt, ResizeMsg)
    assert rt.cols == 220
    assert rt.rows == 50


def test_ping_pong_roundtrip():
    ping = roundtrip(PingMsg(seq=7))
    assert isinstance(ping, PingMsg) and ping.seq == 7
    pong = roundtrip(PongMsg(seq=7))
    assert isinstance(pong, PongMsg) and pong.seq == 7


def test_replay_roundtrip():
    msg = ReplayMsg(from_seq=100)
    rt = roundtrip(msg)
    assert isinstance(rt, ReplayMsg)
    assert rt.from_seq == 100


def test_signal_roundtrip():
    msg = SignalMsg(sig="SIGINT")
    rt = roundtrip(msg)
    assert isinstance(rt, SignalMsg)
    assert rt.sig == "SIGINT"


def test_bye_roundtrip():
    rt = roundtrip(ByeMsg())
    assert isinstance(rt, ByeMsg)


def test_hello_roundtrip():
    msg = HelloMsg(label="mbp — backend", device="iPhone (Lucas)", caps=["resize"])
    rt = roundtrip(msg)
    assert isinstance(rt, HelloMsg)
    assert rt.label == "mbp — backend"
    assert rt.device == "iPhone (Lucas)"
    assert rt.caps == ["resize"]


def test_unknown_type_raises():
    import cbor2
    with pytest.raises(ValueError, match="Unknown message type"):
        decode(cbor2.dumps({"t": "__unknown__"}))


def test_output_binary_data():
    """Binary PTY data (non-UTF8) must survive encode/decode."""
    data = bytes(range(256))
    rt = roundtrip(OutputMsg(seq=1, data=data))
    assert rt.data == data
