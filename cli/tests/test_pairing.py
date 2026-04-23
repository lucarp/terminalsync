import base64
import json
import socket
import pytest
from terminalsync.pairing import (
    make_sid,
    make_label,
    build_payload,
    payload_to_url,
    render_qr_terminal,
    QrPayload,
)


def test_make_sid_is_unique():
    assert make_sid() != make_sid()


def test_make_sid_is_nonempty():
    assert len(make_sid()) > 8


def test_make_label_contains_hostname():
    label = make_label()
    hostname = socket.gethostname().split(".")[0]
    assert hostname in label


def _sample_payload() -> QrPayload:
    pubkey = bytes(32)
    psk = bytes(32)
    cert_der = b"fakecert" * 20
    return build_payload(
        sid="testid123",
        label="mbp — backend",
        host="100.1.2.3",
        port=49721,
        pubkey=pubkey,
        psk=psk,
        cert_der=cert_der,
    )


def test_build_payload_endpoint():
    p = _sample_payload()
    assert p.endpoint == "wss://100.1.2.3:49721/s/testid123"


def test_build_payload_version():
    p = _sample_payload()
    assert p.v == 2


def test_build_payload_pub_is_base64():
    p = _sample_payload()
    decoded = base64.urlsafe_b64decode(p.pub + "==")
    assert len(decoded) == 32


def test_payload_to_url_is_https():
    p = _sample_payload()
    url = payload_to_url(p)
    assert url.startswith("https://")


def test_payload_to_url_contains_pair_param():
    p = _sample_payload()
    url = payload_to_url(p)
    assert "?pair=" in url
    pair_b64 = url.split("?pair=")[1]
    raw = base64.urlsafe_b64decode(pair_b64 + "==")
    obj = json.loads(raw)
    assert obj["v"] == 2
    assert obj["sid"] == "testid123"


def test_render_qr_terminal_contains_block_chars():
    p = _sample_payload()
    url = payload_to_url(p)
    qr = render_qr_terminal(url)
    assert len(qr) > 0
    assert any(c in qr for c in ("█", "▀", "▄", " "))
