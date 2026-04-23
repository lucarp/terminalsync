import sys
import threading
from typing import TextIO


class StatusLine:
    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream or sys.stderr
        self._lock = threading.Lock()

    def update(self, text: str) -> None:
        with self._lock:
            self._stream.write(f"\r\033[K\033[2m[TerminalSync] {text}\033[0m")
            self._stream.flush()

    def clear(self) -> None:
        with self._lock:
            self._stream.write("\r\033[K")
            self._stream.flush()

    def print_pair_info(self, qr_str: str, endpoint: str) -> None:
        """Print QR block and endpoint above the status line."""
        self._stream.write("\n")
        for line in qr_str.splitlines():
            self._stream.write(f"  {line}\n")
        self._stream.write(f"\n  Scan with your phone or visit:\n  \033[1m{endpoint}\033[0m\n\n")
        self._stream.flush()
