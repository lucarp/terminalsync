from dataclasses import dataclass
from typing import Union

import cbor2


@dataclass
class OutputMsg:
    seq: int
    data: bytes


@dataclass
class InputMsg:
    data: bytes


@dataclass
class ResizeMsg:
    cols: int
    rows: int


@dataclass
class PingMsg:
    seq: int


@dataclass
class PongMsg:
    seq: int


@dataclass
class ReplayMsg:
    from_seq: int


@dataclass
class SignalMsg:
    sig: str


@dataclass
class ByeMsg:
    pass


@dataclass
class HelloMsg:
    label: str
    device: str
    caps: list[str]


Message = Union[
    OutputMsg, InputMsg, ResizeMsg, PingMsg, PongMsg,
    ReplayMsg, SignalMsg, ByeMsg, HelloMsg,
]


def encode(msg: Message) -> bytes:
    if isinstance(msg, OutputMsg):
        return cbor2.dumps({"t": "output", "seq": msg.seq, "data": msg.data})
    if isinstance(msg, InputMsg):
        return cbor2.dumps({"t": "input", "data": msg.data})
    if isinstance(msg, ResizeMsg):
        return cbor2.dumps({"t": "resize", "cols": msg.cols, "rows": msg.rows})
    if isinstance(msg, PingMsg):
        return cbor2.dumps({"t": "ping", "seq": msg.seq})
    if isinstance(msg, PongMsg):
        return cbor2.dumps({"t": "pong", "seq": msg.seq})
    if isinstance(msg, ReplayMsg):
        return cbor2.dumps({"t": "replay", "from_seq": msg.from_seq})
    if isinstance(msg, SignalMsg):
        return cbor2.dumps({"t": "signal", "sig": msg.sig})
    if isinstance(msg, ByeMsg):
        return cbor2.dumps({"t": "bye"})
    if isinstance(msg, HelloMsg):
        return cbor2.dumps({"t": "hello", "label": msg.label, "device": msg.device, "caps": msg.caps})
    raise ValueError(f"Unknown message type: {type(msg)}")


def decode(data: bytes) -> Message:
    obj = cbor2.loads(data)
    t = obj.get("t")
    if t == "output":
        return OutputMsg(seq=obj["seq"], data=bytes(obj["data"]))
    if t == "input":
        return InputMsg(data=bytes(obj["data"]))
    if t == "resize":
        return ResizeMsg(cols=obj["cols"], rows=obj["rows"])
    if t == "ping":
        return PingMsg(seq=obj["seq"])
    if t == "pong":
        return PongMsg(seq=obj["seq"])
    if t == "replay":
        return ReplayMsg(from_seq=obj["from_seq"])
    if t == "signal":
        return SignalMsg(sig=obj["sig"])
    if t == "bye":
        return ByeMsg()
    if t == "hello":
        return HelloMsg(label=obj["label"], device=obj["device"], caps=obj.get("caps", []))
    raise ValueError(f"Unknown message type: {t!r}")
