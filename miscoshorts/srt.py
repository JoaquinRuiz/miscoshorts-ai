"""SRT parsing into Whisper-style segments."""

from __future__ import annotations

import re

_SRT_TIME = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})")


def _to_seconds(match: re.Match) -> float:
    h, m, s, ms = match.groups()
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000.0


def parse_srt(srt_text: str) -> list[dict]:
    """Parse SRT text into ``[{"start", "end", "text"}]``."""
    segments = []
    for block in re.split(r"\r?\n\s*\r?\n", (srt_text or "").strip()):
        lines = block.strip().splitlines()
        for i, line in enumerate(lines):
            if "-->" not in line:
                continue
            start_str, end_str = line.split("-->", 1)
            start_m, end_m = _SRT_TIME.search(start_str), _SRT_TIME.search(end_str)
            if start_m and end_m:
                text = " ".join(part.strip() for part in lines[i + 1 :]).strip()
                if text:
                    segments.append({"start": _to_seconds(start_m), "end": _to_seconds(end_m), "text": text})
            break
    return segments
