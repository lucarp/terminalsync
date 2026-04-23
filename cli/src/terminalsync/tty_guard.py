import os
import sys


def assert_interactive_terminal() -> None:
    if not (os.isatty(sys.stdin.fileno()) and os.isatty(sys.stdout.fileno())):
        raise SystemExit(
            "terminalsync must run in an interactive terminal. "
            "Background/daemon usage is not supported by design."
        )
    if os.getppid() == 1:
        raise SystemExit(
            "terminalsync appears to be running detached (parent is init). "
            "Background/daemon usage is not supported by design."
        )
