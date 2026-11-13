import json

import pytest

from miscoshorts.clips import Clip, parse_clips, select_best, strip_thinking, validate_clip


def test_json_object_with_clips():
    clips = parse_clips(
        '{"clips": [{"title": "Gancho", "start": 120.5, "end": 155, "score": 8,'
        ' "reason": "r", "description": "d", "hashtags": ["#ia", "shorts"]}]}'
    )
    assert clips == [Clip(120.5, 155, "Gancho", "r", 8, "d", ["#ia", "#shorts"])]


def test_fenced_json_after_thinking():
    text = '<think>\nlet me think {"start": 1}\n</think>\nAquí va:\n```json\n[{"start": "2:00", "end": "2:35"}]\n```'
    clips = parse_clips(text)
    assert (clips[0].start, clips[0].end) == (120, 155)


def test_json_with_spanish_keys_and_string_numbers():
    clips = parse_clips('{"inicio": "120.5s", "fin": "155,0", "titulo": "T", "razon": "R"}')
    assert (clips[0].start, clips[0].end, clips[0].title, clips[0].reason) == (120.5, 155, "T", "R")


def test_json_embedded_in_prose():
    clips = parse_clips('Claro, aquí tienes: {"clips": [{"start": 10, "end": 45}]} ¡Suerte!')
    assert clips[0].end == 45


@pytest.mark.parametrize(
    "text",
    [
        "TITULO: Gancho\nINICIO: 120.5\nFIN: 155.0\nRAZON: Motivo",
        "TITULO: Gancho\nINICIO: 120.5s\nFIN: 155s\nRAZON: Motivo",
        "**TITULO:** Gancho\n**INICIO:** 120.5\n**FIN:** 155.0\n**RAZON:** Motivo",
        "TÍTULO: Gancho\nINICIO: 2:00.5\nFIN: 2:35\nRAZÓN: Motivo",
    ],
)
def test_legacy_text_format(text):
    clip = parse_clips(text)[0]
    assert (clip.start, clip.end, clip.title, clip.reason) == (120.5, 155, "Gancho", "Motivo")


def test_skips_invalid_items_but_keeps_valid_ones():
    clips = parse_clips('{"clips": [{"start": "soon", "end": 3}, {"title": "x"}, {"start": 5, "end": 40}]}')
    assert [(c.start, c.end) for c in clips] == [(5, 40)]


@pytest.mark.parametrize("text", ["", "no idea", "INICIO: pronto\nFIN: luego", '{"clips": []}'])
def test_nothing_usable_raises(text):
    with pytest.raises(ValueError):
        parse_clips(text)


def test_strip_thinking_variants():
    assert strip_thinking("<think>a</think>ok") == "ok"
    assert strip_thinking("<THINKING>\nx\n</THINKING>\nok") == "ok"
    assert strip_thinking("reasoning without opener</think>ok") == "ok"
    assert strip_thinking(None) == ""


def test_validate_ok():
    assert validate_clip(Clip(10, 45), 600, 30, 60) == []


@pytest.mark.parametrize(
    ("clip", "fragment"),
    [
        (Clip(50, 40), "not after start"),
        (Clip(-1, 40), "negative"),
        (Clip(700, 740), "past the end"),
        (Clip(580, 640), "past the end"),
        (Clip(10, 15), "lasts 5.0s"),
        (Clip(10, 200), "lasts 190.0s"),
    ],
)
def test_validate_problems(clip, fragment):
    problems = validate_clip(clip, 600, 30, 60)
    assert any(fragment in p for p in problems), problems


def test_validate_clamps_end_rounding():
    clip = Clip(560, 601.5)
    assert validate_clip(clip, 600, 30, 60) == []
    assert clip.end == 600


def test_select_best_by_score_without_overlaps():
    a, b, c, d = Clip(0, 40, score=5), Clip(30, 70, score=9), Clip(100, 140, score=7), Clip(200, 240)
    assert select_best([a, b, c, d], 3) == [b, c, d]
    assert select_best([a, b, c, d], 1) == [b]


def test_select_best_keeps_order_without_scores():
    a, b = Clip(100, 140), Clip(0, 40)
    assert select_best([a, b], 2) == [a, b]


@pytest.mark.parametrize(
    ("raw", "score"), [(8, 8), ("7.5", 7.5), (98.2, 9.82), (500, 10), (-3, 0), ("n/a", 0)]
)
def test_score_is_normalised_to_0_10(raw, score):
    clip = parse_clips(f'{{"start": 0, "end": 40, "score": {json.dumps(raw)}}}')[0]
    assert clip.score == pytest.approx(score)
