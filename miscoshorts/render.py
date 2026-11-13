"""Cut, reframe to 9:16, upscale/downscale to the target size and burn in subtitles."""

from __future__ import annotations

import os
from pathlib import Path

from miscoshorts import smartcrop
from miscoshorts.captions import build_captions
from miscoshorts.clips import Clip
from miscoshorts.config import Settings
from miscoshorts.subtitles import caption_clips


def crop_box(src_w: int, src_h: int, target_w: int, target_h: int) -> tuple[int, int]:
    """Size of the largest region of the source with the target aspect ratio."""
    target_ratio = target_w / target_h
    if src_w / src_h > target_ratio:
        return int(round(src_h * target_ratio)), src_h
    return src_w, int(round(src_w / target_ratio))


def _reframe(clip, settings: Settings, log):
    import numpy as np
    from PIL import Image

    src_w, src_h = clip.size
    crop_w, crop_h = crop_box(src_w, src_h, settings.width, settings.height)
    y0 = (src_h - crop_h) // 2

    x_center = None
    mode = settings.crop
    if mode == "smart" or (mode == "auto" and smartcrop.available()):
        if not smartcrop.available():
            log("⚠️  --crop smart necesita OpenCV 4: pip install 'miscoshorts-ai[smartcrop]'. Uso el centro.")
        elif crop_w < src_w:
            x_center = smartcrop.face_track(clip, log=log)
            if x_center is None:
                log("🎯 No se detectan caras: recorte centrado")

    def frame_at(get_frame, t):
        frame = get_frame(t)
        cx = x_center(t) if x_center else src_w / 2
        x0 = int(min(max(cx - crop_w / 2, 0), src_w - crop_w))
        region = frame[y0 : y0 + crop_h, x0 : x0 + crop_w]
        if (crop_w, crop_h) != (settings.width, settings.height):
            region = np.asarray(
                Image.fromarray(region).resize((settings.width, settings.height), Image.LANCZOS)
            )
        return region

    return clip.transform(frame_at, apply_to=[])


def render_clip(video, clip: Clip, segments: list[dict], output: Path, settings: Settings, log=print) -> Path:
    from moviepy import CompositeVideoClip

    # `sub` and `vertical` share the source's file reader: closing them would close `video`,
    # which the caller reuses for the next clip and closes at the end.
    sub = video.subclipped(clip.start, clip.end)
    final = None
    try:
        vertical = _reframe(sub, settings, log)
        captions = build_captions(segments, clip.start, clip.end, max_words=settings.subtitles.max_words)
        layers = caption_clips(captions, (settings.width, settings.height), settings.subtitles)
        final = CompositeVideoClip([vertical, *layers], size=(settings.width, settings.height))
        final = final.with_duration(sub.duration)
        if sub.audio is not None:
            final = final.with_audio(sub.audio)
        output.parent.mkdir(parents=True, exist_ok=True)
        final.write_videofile(
            str(output),
            codec="libx264",
            audio_codec="aac",
            fps=video.fps or 30,
            threads=os.cpu_count() or 4,
            preset="medium",
            ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
            logger="bar",
        )
    finally:
        if final is not None:
            final.close()
    return output
