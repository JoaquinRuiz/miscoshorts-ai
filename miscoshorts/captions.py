"""Turn transcript segments into short word-level captions ("Shorts style")."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Word:
    start: float
    end: float
    text: str


@dataclass
class Caption:
    start: float
    end: float
    words: list[Word]


def approximate_words(segment: dict) -> list[Word]:
    """Spread a segment's words over its duration, proportionally to their length.

    Used when the transcriber gives no word timestamps (e.g. whisper-server SRT).
    """
    tokens = segment.get("text", "").split()
    if not tokens:
        return []
    start, end = float(segment["start"]), float(segment["end"])
    total = sum(len(t) + 1 for t in tokens)
    words, t = [], start
    for token in tokens:
        share = (end - start) * (len(token) + 1) / total
        words.append(Word(t, t + share, token))
        t += share
    words[-1].end = end
    return words


def segment_words(segment: dict) -> list[Word]:
    """Word timestamps of a segment, or an approximation if it has none."""
    raw = segment.get("words") or []
    words = []
    for w in raw:
        text = str(w.get("word", w.get("text", ""))).strip()
        if text and w.get("start") is not None and w.get("end") is not None:
            words.append(Word(float(w["start"]), float(w["end"]), text))
    return words or approximate_words(segment)


_SENTENCE_END = re.compile(r"[.!?…:;]$")


def build_captions(
    segments: list[dict],
    clip_start: float,
    clip_end: float,
    max_words: int = 3,
    max_gap: float = 0.6,
) -> list[Caption]:
    """Group the words inside ``[clip_start, clip_end]`` into captions of up to ``max_words``.

    Times are relative to the clip. A new caption starts after ``max_words`` words, after a
    sentence ends or after a pause longer than ``max_gap`` seconds.
    """
    words: list[Word] = []
    for seg in segments:
        if seg["end"] <= clip_start or seg["start"] >= clip_end:
            continue
        for w in segment_words(seg):
            if w.end <= clip_start or w.start >= clip_end:
                continue
            words.append(
                Word(
                    max(0.0, w.start - clip_start),
                    min(clip_end, w.end) - clip_start,
                    w.text,
                )
            )

    captions: list[Caption] = []
    current: list[Word] = []
    for w in words:
        if current and (
            len(current) >= max_words
            or w.start - current[-1].end > max_gap
            or _SENTENCE_END.search(current[-1].text)
        ):
            captions.append(Caption(current[0].start, current[-1].end, current))
            current = []
        current.append(w)
    if current:
        captions.append(Caption(current[0].start, current[-1].end, current))

    # Close small gaps so captions don't flicker between words.
    for a, b in zip(captions, captions[1:], strict=False):
        if 0 < b.start - a.end <= 0.3:
            a.end = b.start
    return [c for c in captions if c.end > c.start]
