"""Draw "Shorts style" captions with Pillow: a few words at a time, current word highlighted."""

from __future__ import annotations

import platform
from functools import lru_cache
from pathlib import Path

from miscoshorts.captions import Caption
from miscoshorts.config import SubtitleStyle

BUNDLED_FONT = Path(__file__).parent / "assets" / "fonts" / "Anton-Regular.ttf"

_SYSTEM_FONTS = {
    "Darwin": [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ],
    "Windows": ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf"],
    "Linux": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ],
}


@lru_cache(maxsize=16)
def load_font(name: str | None, size: int):
    """Font by path or name, then the bundled Anton, then common system fonts, then Pillow's."""
    from PIL import ImageFont

    candidates = [name] if name else []
    candidates += [str(BUNDLED_FONT)] + _SYSTEM_FONTS.get(platform.system(), [])
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _wrap(words: list[str], font, max_width: float, space: float) -> list[list[int]]:
    lines: list[list[int]] = [[]]
    width = 0.0
    for i, word in enumerate(words):
        w = font.getlength(word)
        if lines[-1] and width + space + w > max_width:
            lines.append([])
            width = 0.0
        width += (space if lines[-1] else 0) + w
        lines[-1].append(i)
    return lines


def render_caption(words: list[str], active: int | None, width: int, height: int, style: SubtitleStyle):
    """RGBA numpy image of one caption, ``width`` wide, with word ``active`` highlighted."""
    import numpy as np
    from PIL import Image, ImageDraw

    size = max(12, int(height * style.size))
    font = load_font(style.font, size)
    stroke = max(1, int(size * style.stroke))
    text = [w.upper() if style.uppercase else w for w in words]
    space = font.getlength(" ")
    lines = _wrap(text, font, width * 0.86, space)

    ascent, descent = font.getmetrics()
    line_h = int((ascent + descent) * 1.05)
    img_h = line_h * len(lines) + stroke * 2
    img = Image.new("RGBA", (width, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    y = stroke
    for line in lines:
        line_w = sum(font.getlength(text[i]) for i in line) + space * (len(line) - 1)
        x = (width - line_w) / 2
        for i in line:
            color = style.highlight if i == active else style.color
            draw.text(
                (x, y),
                text[i],
                font=font,
                fill=color,
                stroke_width=stroke,
                stroke_fill=style.stroke_color,
            )
            x += font.getlength(text[i]) + space
        y += line_h
    return np.array(img)


def caption_clips(captions: list[Caption], video_size: tuple[int, int], style: SubtitleStyle):
    """MoviePy ``ImageClip`` layers for the captions: one per word, so the highlight moves."""
    from moviepy import ImageClip

    width, height = video_size
    layers = []
    for cap in captions:
        words = [w.text for w in cap.words]
        for i, word in enumerate(cap.words):
            start = cap.start if i == 0 else word.start
            end = cap.words[i + 1].start if i + 1 < len(cap.words) else cap.end
            if end <= start:
                continue
            frame = render_caption(words, i, width, height, style)
            y = int(height * style.position - frame.shape[0] / 2)
            layers.append(
                ImageClip(frame, transparent=True)
                .with_start(start)
                .with_duration(end - start)
                .with_position((0, y))
            )
    return layers
