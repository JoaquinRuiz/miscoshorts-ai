"""Follow the speaker: horizontal crop position over time from face detection (OpenCV)."""

from __future__ import annotations

from collections.abc import Callable


def available() -> bool:
    try:
        import cv2
    except ImportError:
        return False
    # OpenCV 5 dropped the Haar cascades from the main package.
    return hasattr(cv2, "CascadeClassifier") and hasattr(cv2, "data")


def smooth_track(
    times: list[float], centers: list[float | None], default: float, dead_zone: float, alpha: float = 0.25
) -> list[float]:
    """Fill gaps, then smooth: hold still unless the face moves more than ``dead_zone``."""
    filled: list[float] = []
    last = next((c for c in centers if c is not None), default)
    for c in centers:
        if c is not None:
            last = c
        filled.append(last)

    smoothed: list[float] = []
    target = position = filled[0] if filled else default
    for c in filled:
        if abs(c - target) > dead_zone:
            target = c
        position += alpha * (target - position)
        smoothed.append(position)
    return smoothed


def make_interpolator(times: list[float], values: list[float]) -> Callable[[float], float]:
    import numpy as np

    t_arr, v_arr = np.asarray(times, dtype=float), np.asarray(values, dtype=float)
    return lambda t: float(np.interp(t, t_arr, v_arr))


def face_track(clip, sample_every: float = 0.25, log=print) -> Callable[[float], float] | None:
    """Return ``x_center(t)`` in source pixels, or ``None`` if no face is found."""
    import cv2

    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    w, h = clip.size
    scale = 360 / h if h > 360 else 1.0  # detect on a small frame: much faster
    times, centers = [], []
    t, found = 0.0, 0
    while t < clip.duration:
        frame = clip.get_frame(t)
        small = cv2.resize(frame, (int(w * scale), int(h * scale)))
        gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6, minSize=(24, 24))
        if len(faces):
            # The biggest face is usually the person talking to the camera.
            x, _, fw, _ = max(faces, key=lambda f: f[2] * f[3])
            centers.append((x + fw / 2) / scale)
            found += 1
        else:
            centers.append(None)
        times.append(t)
        t += sample_every

    if not times or found < max(2, len(times) * 0.2):
        return None
    log(f"🎯 Encuadre inteligente: cara detectada en {found}/{len(times)} muestras")
    track = smooth_track(times, centers, default=w / 2, dead_zone=w * 0.06)
    return make_interpolator(times, track)
