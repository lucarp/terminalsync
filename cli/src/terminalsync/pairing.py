import base64
import hashlib
import json
import os
import socket
import time
from dataclasses import dataclass

import qrcode


@dataclass
class QrPayload:
    v: int
    sid: str
    label: str
    endpoint: str
    pub: str   # base64url-encoded 32 bytes, no padding
    psk: str   # base64url-encoded 32 bytes, no padding
    fpr: str   # first 16 hex chars of SHA-256(cert_der)


def make_sid() -> str:
    ts = f"{int(time.time() * 1000):013x}"
    rnd = os.urandom(8).hex()
    return f"{ts}{rnd}"


def make_label() -> str:
    hostname = socket.gethostname().split(".")[0]
    cwd = os.path.basename(os.getcwd()) or "~"
    return f"{hostname} — {cwd}"


def build_payload(
    sid: str,
    label: str,
    host: str,
    port: int,
    pubkey: bytes,
    psk: bytes,
    cert_der: bytes,
) -> QrPayload:
    return QrPayload(
        v=2,
        sid=sid,
        label=label,
        endpoint=f"wss://{host}:{port}/s/{sid}",
        pub=base64.urlsafe_b64encode(pubkey).decode().rstrip("="),
        psk=base64.urlsafe_b64encode(psk).decode().rstrip("="),
        fpr=hashlib.sha256(cert_der).hexdigest()[:16],
    )


def payload_to_url(p: QrPayload) -> str:
    """Return the HTTPS URL to encode in the QR code."""
    obj = {
        "v": p.v,
        "sid": p.sid,
        "label": p.label,
        "endpoint": p.endpoint,
        "pub": p.pub,
        "psk": p.psk,
        "fpr": p.fpr,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(obj, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    https_base = p.endpoint.replace("wss://", "https://").split("/s/")[0]
    return f"{https_base}/?pair={encoded}"


def render_qr_terminal(data: str) -> str:
    """Render QR code as Unicode half-block characters for terminal output."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=1,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    matrix = qr.get_matrix()

    lines = []
    for y in range(0, len(matrix), 2):
        row1 = matrix[y]
        row2 = matrix[y + 1] if y + 1 < len(matrix) else [False] * len(matrix[0])
        line = ""
        for x in range(len(row1)):
            top, bot = row1[x], row2[x]
            if top and bot:
                line += "█"
            elif top:
                line += "▀"
            elif bot:
                line += "▄"
            else:
                line += " "
        lines.append(line)
    return "\n".join(lines)
