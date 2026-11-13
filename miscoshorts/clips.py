"""Clip proposals: parse what the LLM answers, validate it and pick non-overlapping clips."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

from miscoshorts.timeparse import parse_time

_THINK = re.compile(r"<(think|thinking|reasoning)>.*?</\1>", re.DOTALL | re.IGNORECASE)
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


@dataclass
class Clip:
    start: float
    end: float
    title: str = ""
    reason: str = ""
    score: float = 0.0
    description: str = ""
    hashtags: list[str] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.end - self.start

    def to_dict(self) -> dict:
        return asdict(self)


def strip_thinking(text: str) -> str:
    """Remove ``<think>…</think>`` blocks (and an unclosed leading one) from reasoning models."""
    text = _THINK.sub("", text or "")
    # Some servers cut the opening tag and only leave "...</think>".
    if "</think>" in text.lower():
        text = re.split(r"</think>", text, flags=re.IGNORECASE)[-1]
    return text.strip()


def _extract_json(text: str):
    candidates = [m.group(1) for m in _FENCE.finditer(text)] + [text]
    for candidate in candidates:
        candidate = candidate.strip()
        try:
            return json.loads(candidate)
        except ValueError:
            pass
        # First balanced-looking object or array in the text.
        for opener, closer in (("{", "}"), ("[", "]")):
            start, end = candidate.find(opener), candidate.rfind(closer)
            if start != -1 and end > start:
                try:
                    return json.loads(candidate[start : end + 1])
                except ValueError:
                    continue
    return None


def _first(d: dict, *keys, default=None):
    lowered = {str(k).lower(): v for k, v in d.items()}
    for key in keys:
        if key in lowered and lowered[key] not in (None, ""):
            return lowered[key]
    return default


def _hashtags(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        value = re.split(r"[\s,]+", value)
    tags = []
    for tag in value:
        tag = str(tag).strip()
        if tag:
            tags.append(tag if tag.startswith("#") else f"#{tag}")
    return tags


def _clip_from_dict(d: dict) -> Clip | None:
    start = _first(d, "start", "inicio", "start_time", "begin")
    end = _first(d, "end", "fin", "end_time", "stop")
    if start is None or end is None:
        return None
    try:
        score = float(_first(d, "score", "puntuacion", "puntuación", default=0) or 0)
    except (TypeError, ValueError):
        score = 0.0
    if 10 < score <= 100:  # some models answer on a 0-100 scale despite the prompt
        score /= 10
    score = min(max(score, 0.0), 10.0)
    return Clip(
        start=parse_time(start),
        end=parse_time(end),
        title=str(_first(d, "title", "titulo", "título", default="")).strip(),
        reason=str(_first(d, "reason", "razon", "razón", default="")).strip(),
        score=score,
        description=str(_first(d, "description", "descripcion", "descripción", default="")).strip(),
        hashtags=_hashtags(_first(d, "hashtags", "tags", default=[])),
    )


_LEGACY_FIELD = r"\**\s*{name}\s*\**\s*[:：]\s*\**\s*(.+)"


def _legacy_field(text: str, *names: str) -> str | None:
    for name in names:
        match = re.search(_LEGACY_FIELD.format(name=name), text, re.IGNORECASE)
        if match:
            return match.group(1).strip().strip("*").strip()
    return None


def _parse_legacy(text: str) -> list[Clip]:
    """Fallback for the old ``TITULO: / INICIO: / FIN: / RAZON:`` text format."""
    start = _legacy_field(text, "INICIO", "START")
    end = _legacy_field(text, "FIN", "END")
    if start is None or end is None:
        return []
    number = re.compile(r"[\d:.,]+")
    start_m, end_m = number.search(start), number.search(end)
    if not start_m or not end_m:
        return []
    return [
        Clip(
            start=parse_time(start_m.group(0).rstrip(".,")),
            end=parse_time(end_m.group(0).rstrip(".,")),
            title=_legacy_field(text, "TITULO", "TÍTULO", "TITLE") or "",
            reason=_legacy_field(text, "RAZON", "RAZÓN", "REASON") or "",
        )
    ]


def parse_clips(text: str) -> list[Clip]:
    """Parse an LLM answer into clips. Accepts JSON (object, list, fenced) or the legacy text format.

    Raises ``ValueError`` if nothing usable is found.
    """
    text = strip_thinking(text)
    data = _extract_json(text)
    clips: list[Clip] = []
    if isinstance(data, dict):
        items = _first(data, "clips", "shorts", "segments", "segmentos")
        data = items if isinstance(items, list) else [data]
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                try:
                    clip = _clip_from_dict(item)
                except ValueError:
                    continue
                if clip:
                    clips.append(clip)
    if not clips:
        try:
            clips = _parse_legacy(text)
        except ValueError:
            clips = []
    if not clips:
        raise ValueError(f"could not find any clip in the answer: {text[:300]!r}")
    return clips


def validate_clip(clip: Clip, duration: float | None, min_seconds: float, max_seconds: float) -> list[str]:
    """Return a list of problems (empty if the clip is usable). May clamp ``end`` to the duration."""
    errors = []
    if clip.start < 0:
        errors.append(f"start {clip.start:.1f}s is negative")
    if clip.end <= clip.start:
        errors.append(f"end {clip.end:.1f}s is not after start {clip.start:.1f}s")
    if duration is not None:
        if clip.start >= duration:
            errors.append(f"start {clip.start:.1f}s is past the end of the video ({duration:.1f}s)")
        elif clip.end > duration:
            if clip.end - duration <= 2:
                clip.end = duration  # rounding at the very end of the video
            else:
                errors.append(f"end {clip.end:.1f}s is past the end of the video ({duration:.1f}s)")
    if not errors:
        low, high = min_seconds * 0.75, max_seconds * 1.25
        if not low <= clip.duration <= high:
            errors.append(f"lasts {clip.duration:.1f}s, expected about {min_seconds:g}-{max_seconds:g}s")
    return errors


def overlaps(a: Clip, b: Clip) -> bool:
    return a.start < b.end and b.start < a.end


def select_best(clips: list[Clip], count: int) -> list[Clip]:
    """Best ``count`` clips by score (stable for ties), without overlaps, in score order."""
    ranked = sorted(enumerate(clips), key=lambda ic: (-ic[1].score, ic[0]))
    chosen: list[Clip] = []
    for _, clip in ranked:
        if len(chosen) >= count:
            break
        if not any(overlaps(clip, other) for other in chosen):
            chosen.append(clip)
    return chosen
