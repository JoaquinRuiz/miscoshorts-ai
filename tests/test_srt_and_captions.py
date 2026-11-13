import pytest

from miscoshorts.captions import approximate_words, build_captions
from miscoshorts.srt import parse_srt

SRT = (
    "1\r\n00:00:00,000 --> 00:00:03,600\r\nHola mundo\r\n\r\n"
    "2\n00:01:02,500 --> 00:01:05,000\nlinea uno\nlinea dos\n\n"
    "3\nbad block\n\n"
    "4\n00:01:06.000 --> 00:01:07.000\n\n"
)


def test_parse_srt():
    assert parse_srt(SRT) == [
        {"start": 0.0, "end": 3.6, "text": "Hola mundo"},
        {"start": 62.5, "end": 65.0, "text": "linea uno linea dos"},
    ]


def test_parse_srt_empty():
    assert parse_srt("") == []
    assert parse_srt(None) == []


def test_approximate_words_cover_the_segment():
    words = approximate_words({"start": 10, "end": 12, "text": "a bbb"})
    assert [w.text for w in words] == ["a", "bbb"]
    assert words[0].start == 10 and words[-1].end == 12
    assert words[0].end == pytest.approx(10 + 2 * 2 / 6)  # "a " is 2 of 6 characters of 2 s


def _seg(start, end, *words):
    step = (end - start) / len(words)
    return {
        "start": start,
        "end": end,
        "text": " ".join(words),
        "words": [
            {"word": w, "start": start + i * step, "end": start + (i + 1) * step} for i, w in enumerate(words)
        ],
    }


def test_build_captions_groups_and_offsets():
    segments = [_seg(100, 104, "uno", "dos", "tres", "cuatro"), _seg(104, 106, "cinco.", "seis")]
    caps = build_captions(segments, clip_start=100, clip_end=106, max_words=3)
    assert [[w.text for w in c.words] for c in caps] == [
        ["uno", "dos", "tres"],
        ["cuatro", "cinco."],
        ["seis"],
    ]
    assert caps[0].start == 0 and caps[-1].end == pytest.approx(6)


def test_build_captions_breaks_on_pauses_and_clips_to_range():
    segments = [_seg(0, 2, "a", "b"), _seg(5, 7, "c", "d"), _seg(50, 52, "fuera")]
    caps = build_captions(segments, clip_start=1, clip_end=7, max_words=5)
    assert [[w.text for w in c.words] for c in caps] == [["b"], ["c", "d"]]
    assert caps[0].start == 0  # "b" starts at 1s in the source = 0s in the clip


def test_build_captions_without_word_timestamps():
    caps = build_captions([{"start": 0, "end": 3, "text": "una frase sin palabras"}], 0, 3, max_words=2)
    assert [len(c.words) for c in caps] == [2, 2]
