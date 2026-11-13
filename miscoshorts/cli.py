"""Command line: ``miscoshorts URL_OR_FILE [options]``."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from miscoshorts import __version__
from miscoshorts.clips import Clip, validate_clip
from miscoshorts.config import Settings
from miscoshorts.timeparse import format_time, parse_range, parse_time


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="miscoshorts",
        description="Turn a long video into vertical Shorts with subtitles, picked by AI.",
        epilog="Every option can also be set with environment variables or a .env file (see README).",
    )
    p.add_argument("source", help="YouTube (or any yt-dlp) URL, or a local video file")
    p.add_argument(
        "-o",
        "--output",
        default="short_con_subs.mp4",
        help="output file; with --count N, _1, _2… are appended (default: %(default)s)",
    )
    p.add_argument("-n", "--count", type=int, default=None, help="how many Shorts to make (default: 1)")
    p.add_argument("--start", help="render this segment without asking the AI, e.g. 120 or 2:00")
    p.add_argument("--end", help="end of the segment for --start, e.g. 155 or 2:35")
    p.add_argument("-y", "--yes", action="store_true", help="don't ask: render the AI proposals")
    p.add_argument("--min-seconds", type=float, default=None, help="shortest Short (default: 30)")
    p.add_argument("--max-seconds", type=float, default=None, help="longest Short (default: 60)")

    ai = p.add_argument_group("AI")
    ai.add_argument("--backend", choices=["gemini", "openai"], help="LLM backend (env CEREBRO_BACKEND)")
    ai.add_argument("--model", help="LLM model (env GEMINI_MODEL / OPENAI_MODEL)")
    ai.add_argument(
        "--chunk-chars",
        type=int,
        help="split transcripts longer than this many characters (env MAX_TRANSCRIPT_CHARS)",
    )

    tr = p.add_argument_group("transcription")
    tr.add_argument("--lang", help="spoken language, e.g. es or en (default: auto-detect)")
    tr.add_argument("--whisper-engine", choices=["openai-whisper", "faster-whisper"])
    tr.add_argument("--whisper-model", help="tiny, base, small, medium, large-v3… (default: base)")
    tr.add_argument("--whisper-api", action="store_true", help="use a whisper.cpp server (WHISPER_API_URL)")
    tr.add_argument("--no-cache", action="store_true", help="transcribe again even if cached")

    out = p.add_argument_group("video")
    out.add_argument(
        "--crop",
        choices=["auto", "smart", "center"],
        help="smart follows faces (needs OpenCV); auto = smart if available (default)",
    )
    out.add_argument("--resolution", default=None, help="output size WxH (default: 1080x1920)")
    out.add_argument("--font", help="subtitle font file or name (default: bundled Anton)")
    out.add_argument("--words-per-caption", type=int, help="words shown at once (default: 3)")

    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def settings_from_args(args: argparse.Namespace) -> Settings:
    s = Settings.from_env()
    if args.backend:
        s.backend = args.backend
    if args.model:
        if s.backend == "gemini":
            s.gemini_model = args.model
        else:
            s.openai_model = args.model
    if args.chunk_chars:
        s.chunk_chars = args.chunk_chars
    if args.lang:
        s.language = args.lang
    if args.whisper_engine:
        s.whisper_engine = args.whisper_engine
    if args.whisper_model:
        s.whisper_model = args.whisper_model
    if args.whisper_api:
        s.use_whisper_api = True
    if args.no_cache:
        s.use_cache = False
    if args.crop:
        s.crop = args.crop
    if args.resolution:
        try:
            w, h = (int(v) for v in args.resolution.lower().split("x"))
        except ValueError:
            raise SystemExit(
                f"--resolution debe ser WxH, por ejemplo 1080x1920 (no {args.resolution!r})"
            ) from None
        s.width, s.height = w - w % 2, h - h % 2  # libx264 needs even sizes
    if args.font:
        s.subtitles.font = args.font
    if args.words_per_caption:
        s.subtitles.max_words = max(1, args.words_per_caption)
    if args.count:
        s.count = max(1, args.count)
    if args.min_seconds:
        s.min_seconds = args.min_seconds
    if args.max_seconds:
        s.max_seconds = args.max_seconds
    if s.min_seconds > s.max_seconds:
        raise SystemExit("--min-seconds no puede ser mayor que --max-seconds")
    return s


def manual_clip(start: str, end: str, duration: float) -> Clip:
    clip = Clip(parse_time(start), parse_time(end), title="")
    problems = validate_clip(clip, duration, 0, float("inf"))
    if problems:
        raise ValueError("; ".join(problems))
    return clip


def show_proposals(clips: list[Clip]) -> None:
    print("\n🤖 PROPUESTA DE SHORT:" if len(clips) == 1 else f"\n🤖 PROPUESTAS DE SHORT ({len(clips)}):")
    for i, c in enumerate(clips, 1):
        score = f"⭐ {c.score:g}  " if c.score else ""
        print(f" [{i}] {score}📌 {c.title or '(sin título)'}")
        print(f"     ⏱️  {format_time(c.start)} → {format_time(c.end)}  ({c.duration:.1f}s)")
        if c.reason:
            print(f"     💡 {c.reason}")


def choose(clips: list[Clip], duration: float) -> list[Clip]:
    """Ask the user which clips to render. Returns [] to cancel."""
    if clips:
        hint = (
            "'s' (o Enter) para crearlo"
            if len(clips) == 1
            else "'s' (o Enter) para crearlos todos, números para elegir (ej: 1,3)"
        )
    else:
        print("\n🤖 La IA no ha propuesto ningún segmento válido.")
        hint = "Introduce los tiempos a mano"
    prompt = f"¿Te mola? {hint}, nuevos tiempos (ej: 120-140 o 2:00-2:20), o 'q' para salir: "
    while True:
        try:
            answer = input(prompt).strip().lower()
        except EOFError:
            print()
            return []
        if answer in ("q", "n", "no", "salir", "quit"):
            return []
        if clips and answer in ("", "s", "si", "sí", "y", "yes"):
            return clips
        if clips and all(part.strip().isdigit() for part in answer.split(",")):
            picks = [int(part) for part in answer.split(",")]
            if all(1 <= n <= len(clips) for n in picks):
                return [clips[n - 1] for n in dict.fromkeys(picks)]
            print(f"   Elige números entre 1 y {len(clips)}.")
            continue
        try:
            start, end = parse_range(answer)
            clip = Clip(start, end)
            problems = validate_clip(clip, duration, 0, float("inf"))
            if problems:
                raise ValueError("; ".join(problems))
            return [clip]
        except ValueError as exc:
            print(f"   No lo entiendo ({exc}). Prueba otra vez.")


def output_paths(output: Path, n: int) -> list[Path]:
    if n == 1:
        return [output]
    return [output.with_name(f"{output.stem}_{i}{output.suffix}") for i in range(1, n + 1)]


def write_metadata(path: Path, clip: Clip, source) -> None:
    data = {"source": source.title, "url_or_file": str(source.original), **clip.to_dict()}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    settings = settings_from_args(args)
    if bool(args.start) != bool(args.end):
        raise SystemExit("--start y --end van juntos")

    # Import the heavy modules only once the arguments are valid.
    from miscoshorts.download import get_source
    from miscoshorts.llm import find_clips
    from miscoshorts.render import render_clip
    from miscoshorts.transcribe import transcribe

    output = Path(args.output)
    source = get_source(args.source)
    video = None
    try:
        result = transcribe(source.path, source.id, settings)
        transcript_file = output.parent / "transcripcion_completa.txt"
        transcript_file.parent.mkdir(parents=True, exist_ok=True)
        transcript_file.write_text(f"URL: {args.source}\n{result['text']}\n", encoding="utf-8")

        from moviepy import VideoFileClip

        video = VideoFileClip(str(source.path))
        duration = video.duration

        if args.start:
            selected = [manual_clip(args.start, args.end, duration)]
        else:
            proposals = find_clips(result["segments"], settings, duration=duration)
            if args.yes:
                if not proposals:
                    print("❌ La IA no ha propuesto ningún segmento válido. Usa --start/--end.")
                    return 1
                show_proposals(proposals)
                selected = proposals
            else:
                if proposals:
                    show_proposals(proposals)
                selected = choose(proposals, duration)
            if not selected:
                print("Cancelado.")
                return 0

        paths = output_paths(output, len(selected))
        for clip, path in zip(selected, paths, strict=True):
            print(f"\n🚀 Cocinando el Short {format_time(clip.start)} → {format_time(clip.end)} en {path}...")
            render_clip(video, clip, result["segments"], path, settings)
            write_metadata(path.with_suffix(".json"), clip, source)
            print(f"🎉 ¡Vídeo listo: {path}!")
            if clip.title or clip.description or clip.hashtags:
                print(f"   📌 {clip.title}")
                if clip.description:
                    print(f"   📝 {clip.description}")
                if clip.hashtags:
                    print(f"   🏷️  {' '.join(clip.hashtags)}")
        return 0
    finally:
        if video is not None:
            video.close()
        if source.temp_dir is not None:
            shutil.rmtree(source.temp_dir, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except KeyboardInterrupt:
        print("\nCancelado.")
        return 130
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
