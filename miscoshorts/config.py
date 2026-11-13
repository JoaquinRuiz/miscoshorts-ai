"""Settings from environment variables (and an optional ``.env``), overridable from the CLI."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(Path.cwd() / ".env", override=False)


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _env_bool(name: str, default: bool) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on", "si", "sí")


def _env_float(name: str, default: float) -> float:
    value = _env(name)
    return float(value) if value is not None else default


def _env_int(name: str, default: int) -> int:
    value = _env(name)
    return int(value) if value is not None else default


@dataclass
class SubtitleStyle:
    font: str | None = None  # path or font name; None = bundled Anton, then system fonts
    size: float = 0.06  # fraction of the video height
    color: str = "white"
    highlight: str = "#FFD400"
    stroke_color: str = "black"
    stroke: float = 0.12  # fraction of the font size
    position: float = 0.68  # vertical centre of the caption, fraction of the height
    max_words: int = 3
    uppercase: bool = True


@dataclass
class Settings:
    # LLM
    backend: str = "gemini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    openai_base_url: str = "http://localhost:11434/v1"
    openai_model: str = "qwen3:30b"
    openai_api_key: str = "none"
    chunk_chars: int | None = None  # None = backend default
    temperature: float = 0.7
    # Transcription
    use_whisper_api: bool = False
    whisper_api_url: str = "http://localhost:9191/inference"
    whisper_engine: str = "openai-whisper"
    whisper_model: str = "base"
    language: str | None = None
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".cache" / "miscoshorts")
    use_cache: bool = True
    # Clips and rendering
    count: int = 1
    min_seconds: float = 30
    max_seconds: float = 60
    width: int = 1080
    height: int = 1920
    crop: str = "auto"  # auto | smart | center
    subtitles: SubtitleStyle = field(default_factory=SubtitleStyle)

    @property
    def llm_model(self) -> str:
        return self.gemini_model if self.backend == "gemini" else self.openai_model

    @property
    def effective_chunk_chars(self) -> int:
        if self.chunk_chars:
            return self.chunk_chars
        # Gemini has a huge context; local servers often default to 4k-8k tokens.
        return 400_000 if self.backend == "gemini" else 10_000

    @classmethod
    def from_env(cls) -> Settings:
        _load_dotenv()
        style = SubtitleStyle(
            font=_env("SUBTITLE_FONT"),
            size=_env_float("SUBTITLE_SIZE", SubtitleStyle.size),
            color=_env("SUBTITLE_COLOR", SubtitleStyle.color),
            highlight=_env("SUBTITLE_HIGHLIGHT", SubtitleStyle.highlight),
            stroke_color=_env("SUBTITLE_STROKE_COLOR", SubtitleStyle.stroke_color),
            position=_env_float("SUBTITLE_POSITION", SubtitleStyle.position),
            max_words=_env_int("SUBTITLE_WORDS", SubtitleStyle.max_words),
            uppercase=_env_bool("SUBTITLE_UPPERCASE", SubtitleStyle.uppercase),
        )
        cache_dir = _env("MISCOSHORTS_CACHE_DIR")
        chunk = _env("MAX_TRANSCRIPT_CHARS")
        return cls(
            backend=_env("CEREBRO_BACKEND", "gemini").lower(),
            gemini_api_key=_env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY"),
            gemini_model=_env("GEMINI_MODEL", cls.gemini_model),
            openai_base_url=_env("OPENAI_BASE_URL", cls.openai_base_url),
            openai_model=_env("OPENAI_MODEL", cls.openai_model),
            openai_api_key=_env("OPENAI_API_KEY", cls.openai_api_key),
            chunk_chars=int(chunk) if chunk else None,
            use_whisper_api=_env_bool("USE_WHISPER_API", False),
            whisper_api_url=_env("WHISPER_API_URL", cls.whisper_api_url),
            whisper_engine=_env("WHISPER_ENGINE", cls.whisper_engine).lower(),
            whisper_model=_env("WHISPER_MODEL", cls.whisper_model),
            language=_env("WHISPER_LANGUAGE"),
            cache_dir=Path(cache_dir).expanduser() if cache_dir else Path.home() / ".cache" / "miscoshorts",
            crop=_env("CROP_MODE", cls.crop).lower(),
            subtitles=style,
        )
