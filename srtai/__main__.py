"""Entry point: ``python -m srtai`` opens the app; ``python -m srtai <command>`` runs the CLI."""
from __future__ import annotations

import sys

CLI_COMMANDS = {"translate", "models", "providers", "languages", "set-key", "selftest",
                "-h", "--help", "--version", "-v", "--verbose"}


def _attach_console() -> None:
    """The Windows .exe has no console; reuse the terminal it was started from for CLI output."""
    if not (getattr(sys, "frozen", False) and sys.platform == "win32" and sys.stdout is None):
        return
    import ctypes
    import os

    if ctypes.windll.kernel32.AttachConsole(-1):
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)
        sys.stderr = sys.stdout
        print()
    else:
        sys.stdout = sys.stderr = open(os.devnull, "w")


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in CLI_COMMANDS:
        _attach_console()
        from .cli import main as cli_main

        return cli_main(sys.argv[1:])
    from .gui.app import run

    return run(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
