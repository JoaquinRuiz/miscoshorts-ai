import os
import re
import subprocess
import tempfile

import requests

# Endpoint of a whisper.cpp `whisper-server` (or compatible) instance.
WHISPER_API_URL = os.getenv("WHISPER_API_URL", "http://localhost:9191/inference")

_SRT_TIME = re.compile(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})")


def _srt_time_to_seconds(match):
    h, m, s, ms = map(int, match.groups())
    return h * 3600 + m * 60 + s + ms / 1000.0


def parse_srt(srt_text):
    """Parse SRT text into Whisper-style segments: [{"start", "end", "text"}]."""
    segments = []
    blocks = re.split(r"\r?\n\s*\r?\n", srt_text.strip())
    for block in blocks:
        lines = block.strip().splitlines()
        # Find the "00:00:00,000 --> 00:00:03,600" line (usually the 2nd one).
        for i, line in enumerate(lines):
            if "-->" in line:
                start_str, end_str = line.split("-->", 1)
                start_m = _SRT_TIME.search(start_str)
                end_m = _SRT_TIME.search(end_str)
                if start_m and end_m:
                    segments.append({
                        "start": _srt_time_to_seconds(start_m),
                        "end": _srt_time_to_seconds(end_m),
                        "text": " ".join(lines[i + 1:]).strip(),
                    })
                break
    return segments


def _extract_audio(video_path):
    """Extract 16 kHz mono WAV (the format whisper.cpp expects) using ffmpeg."""
    fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", video_path,
         "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav_path],
        check=True,
    )
    return wav_path


def _transcribe_api(video_path, api_url):
    wav_path = _extract_audio(video_path)
    try:
        with open(wav_path, "rb") as f:
            response = requests.post(
                api_url,
                files={"file": ("audio.wav", f, "audio/wav")},
                data={"response_format": "srt"},
                timeout=3600,
            )
        response.raise_for_status()
    finally:
        os.remove(wav_path)

    segments = parse_srt(response.text)
    if not segments:
        raise RuntimeError(
            f"Whisper API at {api_url} returned no parseable SRT segments. "
            f"Response starts with: {response.text[:200]!r}"
        )
    return {
        "text": " ".join(seg["text"] for seg in segments),
        "segments": segments,
    }


def _transcribe_local(video_path):
    import whisper
    model = whisper.load_model("base")
    return model.transcribe(video_path)


def transcribe_and_save(video_path, url_video, use_api=False, api_url=WHISPER_API_URL):
    """
    Transcribe a video with local Whisper (default) or a remote whisper-server.

    Always returns a Whisper-style dict with ``text`` and ``segments``
    (each segment has ``start``, ``end`` and ``text``), so every cerebro
    backend and the subtitle generator work the same regardless of the source.
    Also writes the full transcription to ``transcripcion_completa.txt``.
    """
    if use_api:
        result = _transcribe_api(video_path, api_url)
    else:
        result = _transcribe_local(video_path)

    with open("transcripcion_completa.txt", "w", encoding="utf-8") as f:
        f.write(f"URL: {url_video}\n")
        f.write(result["text"])

    return result
