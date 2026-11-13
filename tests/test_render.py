"""Render a tiny synthetic video end to end (needs MoviePy and FFmpeg; skipped otherwise)."""

import shutil

import pytest

moviepy = pytest.importorskip("moviepy")

from miscoshorts.clips import Clip  # noqa: E402
from miscoshorts.config import Settings, SubtitleStyle  # noqa: E402
from miscoshorts.render import render_clip  # noqa: E402
from miscoshorts.subtitles import load_font, render_caption  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")


def test_render_caption_highlights_and_wraps():
    style = SubtitleStyle()
    img = render_caption(["una", "frase", "bastante", "larga", "para", "partir"], 1, 360, 640, style)
    assert img.shape[1] == 360 and img.shape[2] == 4
    assert img[..., 3].max() == 255  # something was drawn
    one_line = render_caption(["hola"], 0, 360, 640, style)
    assert img.shape[0] > one_line.shape[0]  # long caption wrapped onto more lines


def test_bundled_font_loads():
    font = load_font(None, 40)
    assert "Anton" in " ".join(font.getname())


def test_render_clip(tmp_path):
    import numpy as np
    from moviepy import AudioClip, ColorClip, VideoFileClip

    src = tmp_path / "src.mp4"
    video = ColorClip((320, 180), color=(30, 90, 200), duration=3).with_fps(24)
    tone = AudioClip(lambda t: np.sin(2 * np.pi * 440 * t)[..., None] * [1, 1], duration=3, fps=22050)
    video.with_audio(tone).write_videofile(str(src), codec="libx264", audio_codec="aac", logger=None)

    segments = [
        {
            "start": 0.5,
            "end": 2.5,
            "text": "hola qué tal",
            "words": [
                {"word": "hola", "start": 0.5, "end": 1.0},
                {"word": "qué", "start": 1.0, "end": 1.5},
                {"word": "tal", "start": 1.5, "end": 2.5},
            ],
        }
    ]
    settings = Settings(width=270, height=480, crop="center")
    source = VideoFileClip(str(src))
    try:
        out = render_clip(
            source, Clip(0.5, 2.5), segments, tmp_path / "out.mp4", settings, log=lambda *_: None
        )
        # The source is still usable after rendering (the next clip reuses it).
        assert source.get_frame(2.9).shape == (180, 320, 3)
    finally:
        source.close()

    result = VideoFileClip(str(out))
    try:
        assert tuple(result.size) == (270, 480)
        assert result.duration == pytest.approx(2.0, abs=0.15)
        assert result.fps == pytest.approx(24)
        assert result.audio is not None
        # The caption is drawn around 68% of the height: not just the flat blue background.
        row = result.get_frame(0.7)[int(480 * 0.68)]
        assert np.abs(row.astype(int) - [30, 90, 200]).sum(axis=1).max() > 100
    finally:
        result.close()
