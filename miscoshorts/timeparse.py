"""Parsing of human-written times and ranges: ``120``, ``120.5s``, ``2:00``, ``1:02:03,5``."""

from __future__ import annotations

import re

_TIME = re.compile(r"^\s*(?:(\d+):)?(?:(\d+):)?(\d+(?:[.,]\d+)?)\s*s?\s*$", re.IGNORECASE)


def parse_time(value: str | float | int) -> float:
    """Parse seconds or ``[h:]m:s`` into seconds. Raises ``ValueError`` if invalid."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value < 0:
            raise ValueError(f"negative time: {value}")
        return float(value)
    text = str(value).strip().strip("*`\"'[]").strip()
    match = _TIME.match(text)
    if not match:
        raise ValueError(f"invalid time: {value!r}")
    a, b, seconds = match.groups()
    seconds = float(seconds.replace(",", "."))
    if a is not None and b is not None:  # h:m:s
        return int(a) * 3600 + int(b) * 60 + seconds
    if a is not None:  # m:s
        return int(a) * 60 + seconds
    return seconds


def parse_range(text: str) -> tuple[float, float]:
    """Parse ``start-end`` (``120-140``, ``2:00 - 2:20``, ``2:00 a 2:20``)."""
    parts = re.split(r"\s*(?:-|–|—|\bto\b|\ba\b)\s*", text.strip(), maxsplit=1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"expected 'start-end', got {text!r}")
    return parse_time(parts[0]), parse_time(parts[1])


def format_time(seconds: float) -> str:
    """Format seconds as ``m:ss.s`` (or ``h:mm:ss.s``)."""
    seconds = max(0.0, seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{int(h)}:{int(m):02d}:{s:04.1f}"
    return f"{int(m)}:{s:04.1f}"
