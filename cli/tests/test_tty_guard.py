import os
import sys
import pytest
from unittest.mock import patch
from terminalsync.tty_guard import assert_interactive_terminal


def test_raises_when_stdin_not_tty():
    with patch("sys.stdin.fileno", return_value=0):
        with patch("sys.stdout.fileno", return_value=1):
            with patch("os.isatty", side_effect=lambda fd: fd != 0):  # stdin is not a tty
                with pytest.raises(SystemExit, match="interactive terminal"):
                    assert_interactive_terminal()


def test_raises_when_stdout_not_tty():
    with patch("sys.stdin.fileno", return_value=0):
        with patch("sys.stdout.fileno", return_value=1):
            with patch("os.isatty", side_effect=lambda fd: fd != 1):  # stdout is not a tty
                with pytest.raises(SystemExit, match="interactive terminal"):
                    assert_interactive_terminal()


def test_raises_when_parent_is_init():
    with patch("sys.stdin.fileno", return_value=0):
        with patch("sys.stdout.fileno", return_value=1):
            with patch("os.isatty", return_value=True):
                with patch("os.getppid", return_value=1):
                    with pytest.raises(SystemExit, match="detached"):
                        assert_interactive_terminal()


def test_passes_when_interactive():
    with patch("sys.stdin.fileno", return_value=0):
        with patch("sys.stdout.fileno", return_value=1):
            with patch("os.isatty", return_value=True):
                with patch("os.getppid", return_value=1234):
                    assert_interactive_terminal()  # must not raise
