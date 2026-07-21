"""Command-line entry point for MEYES."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from meyes import __version__


def main(argv: Sequence[str] | None = None) -> int:
    """Handle safe metadata commands or start the desktop application."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments == ["--version"]:
        print(f"MEYES {__version__}")
        return 0
    if arguments == ["--diagnose-install"]:
        from meyes.install_diagnostics import print_install_diagnostics

        return print_install_diagnostics()

    from meyes.application import run

    qt_arguments = sys.argv if argv is None else ["meyes", *arguments]
    return run(qt_arguments)


if __name__ == "__main__":
    raise SystemExit(main())
