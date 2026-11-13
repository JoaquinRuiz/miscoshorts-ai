from pathlib import Path

import pytest

from miscoshorts import cli
from miscoshorts.clips import Clip
from miscoshorts.render import crop_box


def test_settings_from_args_overrides_env(monkeypatch):
    monkeypatch.setenv("CEREBRO_BACKEND", "gemini")
    monkeypatch.setenv("WHISPER_MODEL", "small")
    args = cli.build_parser().parse_args(
        ["video.mp4", "--backend", "openai", "--model", "llama3.1:8b", "-n", "3", "--resolution", "721x1281"]
    )
    s = cli.settings_from_args(args)
    assert (s.backend, s.openai_model, s.count, s.whisper_model) == ("openai", "llama3.1:8b", 3, "small")
    assert (s.width, s.height) == (720, 1280)


def test_output_paths():
    assert cli.output_paths(Path("out/s.mp4"), 1) == [Path("out/s.mp4")]
    assert cli.output_paths(Path("s.mp4"), 2) == [Path("s_1.mp4"), Path("s_2.mp4")]


def test_manual_clip_validation():
    assert cli.manual_clip("2:00", "2:20", 600) == Clip(120, 140)
    with pytest.raises(ValueError):
        cli.manual_clip("140", "120", 600)
    with pytest.raises(ValueError):
        cli.manual_clip("590", "700", 600)


def _answers(monkeypatch, *values):
    it = iter(values)
    monkeypatch.setattr("builtins.input", lambda _prompt: next(it))


def test_choose_accepts_all_pick_or_custom(monkeypatch, capsys):
    clips = [Clip(0, 40), Clip(100, 140)]
    _answers(monkeypatch, "")
    assert cli.choose(clips, 600) == clips
    _answers(monkeypatch, "2,2")
    assert cli.choose(clips, 600) == [clips[1]]
    _answers(monkeypatch, "7", "abc", "140-120", "2:00-2:20")
    assert cli.choose(clips, 600) == [Clip(120, 140)]
    _answers(monkeypatch, "q")
    assert cli.choose(clips, 600) == []


def test_choose_without_proposals_needs_times(monkeypatch):
    _answers(monkeypatch, "s", "10-20")
    assert cli.choose([], 600) == [Clip(10, 20)]


def test_choose_eof_cancels(monkeypatch):
    def eof(_prompt):
        raise EOFError

    monkeypatch.setattr("builtins.input", eof)
    assert cli.choose([Clip(0, 40)], 600) == []


@pytest.mark.parametrize(
    ("src", "target", "box"),
    [
        ((1920, 1080), (1080, 1920), (608, 1080)),
        ((1280, 720), (1080, 1920), (405, 720)),
        ((1080, 1920), (1080, 1920), (1080, 1920)),
        ((1080, 2400), (1080, 1920), (1080, 1920)),
    ],
)
def test_crop_box(src, target, box):
    assert crop_box(*src, *target) == box
