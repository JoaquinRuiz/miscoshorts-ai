"""Get the source video: download it from a URL with yt-dlp, or use a local file."""

from __future__ import annotations

import hashlib
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

# Best MP4 video + M4A audio merged by yt-dlp (needs FFmpeg), falling back to the best single file.
FORMAT = "bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"


@dataclass
class Source:
    path: Path
    id: str  # stable id, used as the transcript cache key
    title: str
    temp_dir: Path | None = None  # set when downloaded; deleted after rendering
    original: str = ""  # the URL or path as given


def is_url(value: str) -> bool:
    return bool(re.match(r"^https?://", value.strip(), re.IGNORECASE))


def local_id(path: Path) -> str:
    stat = path.stat()
    key = f"{path.resolve()}|{stat.st_size}|{int(stat.st_mtime)}"
    return "file-" + hashlib.sha1(key.encode()).hexdigest()[:16]


def get_source(value: str, log=print) -> Source:
    if not is_url(value):
        path = Path(value).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"No existe el archivo ni es una URL: {value}")
        log(f"📂 Usando vídeo local: {path}")
        return Source(path=path, id=local_id(path), title=path.stem, original=value)

    import yt_dlp

    log(f"📥 Descargando vídeo: {value}...")
    temp_dir = Path(tempfile.mkdtemp(prefix="miscoshorts-"))
    opts = {
        "format": FORMAT,
        "merge_output_format": "mp4",
        "outtmpl": str(temp_dir / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(value, download=True)
        path = Path(ydl.prepare_filename(info)).with_suffix(".mp4")
    if not path.exists():  # e.g. single-file formats with another extension
        files = sorted(temp_dir.iterdir())
        if not files:
            raise RuntimeError("yt-dlp no ha descargado ningún archivo")
        path = files[0]
    height = info.get("height")
    log(f"   {info.get('title', '')} ({height}p)" if height else f"   {info.get('title', '')}")
    return Source(
        path=path,
        id=f"{info.get('extractor_key', 'url').lower()}-{info['id']}",
        title=info.get("title") or info["id"],
        temp_dir=temp_dir,
        original=value,
    )
