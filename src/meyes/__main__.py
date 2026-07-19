"""Command-line entry point for MEYES."""

from meyes.application import run


def main() -> int:
    """Start the MEYES desktop application."""
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
