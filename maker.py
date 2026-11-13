"""Backwards-compatible entry point: ``python maker.py URL`` == ``miscoshorts URL``."""

from miscoshorts.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
