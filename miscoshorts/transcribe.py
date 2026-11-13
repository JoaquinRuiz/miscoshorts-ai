"""Transcription with local Whisper, faster-whisper or a whisper.cpp server, with a disk cache.

Every engine returns a Whisper-style dict: ``{"text", "language", "segments"}`` where each
segment has ``start``, ``end``, ``text`` and, when available, ``words`` (``word``, ``start``, ``end``).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from miscoshorts.config import Settings
from miscoshorts.srt import parse_srt


def _extract_audio(video_path: Path) -> Path:
    """16 kHz mono WAV, the format whisper.cpp expects."""
    fd, wav = tempfile.mkstemp(suffix=".wav", prefix="miscoshorts-")
    os.close(fd)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            wav,
        ],
        check=True,
    )
    return Path(wav)


def _load_audio(video_path: Path):
    """Decode the audio to 16 kHz mono float32 with FFmpeg (no PyAV needed)."""
    import numpy as np

    out = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-loglevel",
            "error",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "f32le",
            "-",
        ],
        check=True,
        capture_output=True,
    ).stdout
    return np.frombuffer(out, dtype=np.float32)


def _whisper_server(video_path: Path, settings: Settings) -> dict:
    import requests

    wav = _extract_audio(video_path)
    data = {"response_format": "srt"}
    if settings.language:
        data["language"] = settings.language
    try:
        with open(wav, "rb") as f:
            response = requests.post(
                settings.whisper_api_url,
                files={"file": ("audio.wav", f, "audio/wav")},
                data=data,
                timeout=3600,
            )
        response.raise_for_status()
    finally:
        wav.unlink(missing_ok=True)
    segments = parse_srt(response.text)
    if not segments:
        raise RuntimeError(
            f"whisper-server en {settings.whisper_api_url} no ha devuelto segmentos SRT. "
            f"Respuesta: {response.text[:200]!r}"
        )
    return {
        "text": " ".join(s["text"] for s in segments),
        "language": settings.language,
        "segments": segments,
    }


def _openai_whisper(video_path: Path, settings: Settings) -> dict:
    import whisper

    model = whisper.load_model(settings.whisper_model)
    result = model.transcribe(str(video_path), word_timestamps=True, language=settings.language)
    return {
        "text": result["text"].strip(),
        "language": result.get("language"),
        "segments": [
            {
                "start": float(s["start"]),
                "end": float(s["end"]),
                "text": s["text"].strip(),
                "words": [
                    {"word": w["word"].strip(), "start": float(w["start"]), "end": float(w["end"])}
                    for w in s.get("words", [])
                ],
            }
            for s in result["segments"]
        ],
    }


def _faster_whisper(video_path: Path, settings: Settings) -> dict:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "WHISPER_ENGINE=faster-whisper necesita el extra: pip install 'miscoshorts-ai[faster]'"
        ) from exc

    model = WhisperModel(settings.whisper_model, device="auto", compute_type="int8")
    # Pass decoded samples: faster-whisper's own decoder (PyAV) breaks with some av versions.
    raw_segments, info = model.transcribe(
        _load_audio(video_path), word_timestamps=True, language=settings.language, vad_filter=True
    )
    segments = [
        {
            "start": float(s.start),
            "end": float(s.end),
            "text": s.text.strip(),
            "words": [
                {"word": w.word.strip(), "start": float(w.start), "end": float(w.end)}
                for w in (s.words or [])
            ],
        }
        for s in raw_segments
    ]
    return {
        "text": " ".join(s["text"] for s in segments),
        "language": info.language,
        "segments": segments,
    }


def engine_label(settings: Settings) -> str:
    if settings.use_whisper_api:
        return f"whisper-server ({settings.whisper_api_url})"
    return f"{settings.whisper_engine} ({settings.whisper_model})"


def cache_path(source_id: str, settings: Settings) -> Path:
    key = json.dumps([engine_label(settings), settings.language or "auto"], sort_keys=True).encode()
    digest = hashlib.sha1(key).hexdigest()[:10]
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in source_id)
    return settings.cache_dir / "transcripts" / f"{safe_id}-{digest}.json"


def transcribe(video_path: Path, source_id: str, settings: Settings, log=print) -> dict:
    cached = cache_path(source_id, settings)
    if settings.use_cache and cached.exists():
        log(f"♻️  Transcripción en caché ({engine_label(settings)})")
        return json.loads(cached.read_text(encoding="utf-8"))

    log(f"🔍 Transcribiendo con {engine_label(settings)}...")
    if settings.use_whisper_api:
        result = _whisper_server(video_path, settings)
    elif settings.whisper_engine == "faster-whisper":
        result = _faster_whisper(video_path, settings)
    elif settings.whisper_engine == "openai-whisper":
        result = _openai_whisper(video_path, settings)
    else:
        raise ValueError(
            f"WHISPER_ENGINE no soportado: {settings.whisper_engine!r} "
            "(usa 'openai-whisper' o 'faster-whisper')"
        )
    if not result["segments"]:
        raise RuntimeError("La transcripción está vacía: ¿el vídeo tiene voz?")

    if settings.use_cache:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result
