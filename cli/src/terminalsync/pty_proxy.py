import asyncio
import fcntl
import os
import pty
import signal
import struct
import sys
import termios
import tty
from collections import deque
from typing import Callable

SCROLLBACK_LIMIT = 1 * 1024 * 1024  # 1 MB


class PtyProxy:
    def __init__(
        self,
        command: list[str],
        mirror_local: bool = True,
        scrollback_limit: int = SCROLLBACK_LIMIT,
    ) -> None:
        self._command = command
        self._mirror_local = mirror_local
        self._scrollback_limit = scrollback_limit
        self._master_fd: int = -1
        self._child_pid: int = -1
        self._seq: int = 0
        self._scrollback: deque[tuple[int, bytes]] = deque()
        self._scrollback_size: int = 0
        self._output_callbacks: list[Callable[[int, bytes], None]] = []
        self._done: asyncio.Event | None = None

    def add_output_callback(self, cb: Callable[[int, bytes], None]) -> None:
        self._output_callbacks.append(cb)

    def remove_output_callback(self, cb: Callable[[int, bytes], None]) -> None:
        if cb in self._output_callbacks:
            self._output_callbacks.remove(cb)

    async def start(self) -> None:
        self._done = asyncio.Event()

        if self._mirror_local:
            old_tty = termios.tcgetattr(sys.stdin.fileno())

        self._master_fd, slave_fd = pty.openpty()

        self._child_pid = os.fork()
        if self._child_pid == 0:
            os.close(self._master_fd)
            os.setsid()
            fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
            for fd in range(3):
                os.dup2(slave_fd, fd)
            if slave_fd > 2:
                os.close(slave_fd)
            os.execvp(self._command[0], self._command)
            os._exit(1)

        os.close(slave_fd)

        if self._mirror_local:
            tty.setraw(sys.stdin.fileno())

        try:
            await self._run_loop()
        finally:
            if self._mirror_local:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)
            try:
                os.close(self._master_fd)
            except OSError:
                pass
            self._master_fd = -1

    async def _run_loop(self) -> None:
        loop = asyncio.get_event_loop()

        def on_pty_readable() -> None:
            try:
                data = os.read(self._master_fd, 4096)
                if data:
                    self._on_output(data)
            except OSError:
                self._done.set()

        def on_stdin_readable() -> None:
            try:
                data = os.read(sys.stdin.fileno(), 256)
                if data and self._master_fd >= 0:
                    os.write(self._master_fd, data)
                elif not data:  # EOF — terminal closed
                    self._done.set()
            except OSError:
                self._done.set()

        loop.add_reader(self._master_fd, on_pty_readable)
        if self._mirror_local:
            loop.add_reader(sys.stdin.fileno(), on_stdin_readable)

        await self._done.wait()

        loop.remove_reader(self._master_fd)
        if self._mirror_local:
            try:
                loop.remove_reader(sys.stdin.fileno())
            except Exception:
                pass

    def _on_output(self, data: bytes) -> None:
        if self._mirror_local:
            os.write(sys.stdout.fileno(), data)

        self._seq += 1
        self._scrollback.append((self._seq, data))
        self._scrollback_size += len(data)

        while self._scrollback_size > self._scrollback_limit and self._scrollback:
            _, old = self._scrollback.popleft()
            self._scrollback_size -= len(old)

        for cb in list(self._output_callbacks):
            cb(self._seq, data)

    def get_scrollback_from(self, from_seq: int) -> list[tuple[int, bytes]]:
        return [(s, d) for s, d in self._scrollback if s >= from_seq]

    def write_input(self, data: bytes) -> None:
        if self._master_fd >= 0:
            os.write(self._master_fd, data)

    def resize(self, cols: int, rows: int) -> None:
        if self._master_fd >= 0:
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self._master_fd, termios.TIOCSWINSZ, winsize)

    def send_signal(self, sig: str) -> None:
        if self._child_pid > 0:
            try:
                os.kill(self._child_pid, getattr(signal, sig))
            except ProcessLookupError:
                pass

    def terminate(self) -> None:
        if self._child_pid > 0:
            try:
                os.kill(self._child_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        if self._done:
            self._done.set()

    @property
    def last_seq(self) -> int:
        return self._seq
