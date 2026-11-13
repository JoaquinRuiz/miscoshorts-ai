from miscoshorts.config import Settings
from miscoshorts.llm import chunk_segments, find_clips, format_transcript


def segments(n, length=10, text="palabra " * 10):
    return [{"start": i * length, "end": (i + 1) * length, "text": text.strip()} for i in range(n)]


class FakeBackend:
    name = "fake"

    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts = []

    def complete(self, prompt):
        self.prompts.append(prompt)
        return self.answers.pop(0)


def test_format_transcript():
    assert format_transcript([{"start": 1, "end": 2.25, "text": " hola "}]) == "[1.0-2.2] hola"


def test_chunk_segments_fits_and_overlaps():
    segs = segments(60)
    chunks = chunk_segments(segs, max_chars=1000, overlap_seconds=30)
    assert len(chunks) > 1
    for chunk in chunks:
        assert sum(len(s["text"]) + 20 for s in chunk) <= 1000
    assert chunks[0][-1] is segs[len(chunks[0]) - 1]
    # The next chunk starts within the overlap window and everything is covered.
    assert chunks[1][0]["start"] >= chunks[0][-1]["end"] - 30
    assert chunks[1][0]["start"] < chunks[0][-1]["end"]
    assert chunks[-1][-1] is segs[-1]


def test_chunk_segments_single_chunk():
    segs = segments(5)
    assert chunk_segments(segs, max_chars=10_000) == [segs]


def test_find_clips_retries_after_invalid_answer():
    backend = FakeBackend("no sé", '{"clips": [{"start": 10, "end": 45, "title": "ok"}]}')
    clips = find_clips(segments(10), Settings(), duration=100, backend=backend, log=lambda *_: None)
    assert [c.title for c in clips] == ["ok"]
    assert len(backend.prompts) == 2 and "no era válida" in backend.prompts[1]


def test_find_clips_retries_with_validation_errors():
    backend = FakeBackend('{"clips": [{"start": 90, "end": 300}]}', '{"clips": [{"start": 40, "end": 80}]}')
    clips = find_clips(segments(10), Settings(), duration=100, backend=backend, log=lambda *_: None)
    assert [(c.start, c.end) for c in clips] == [(40, 80)]
    assert "past the end" in backend.prompts[1]


def test_find_clips_gives_up_after_two_attempts():
    backend = FakeBackend("nada", "tampoco")
    assert find_clips(segments(10), Settings(), duration=100, backend=backend, log=lambda *_: None) == []


def test_find_clips_merges_chunks_by_score():
    settings = Settings(count=2, chunk_chars=1000)
    answers = iter(
        [
            '{"clips": [{"start": 0, "end": 40, "score": 3}]}',
            '{"clips": [{"start": 300, "end": 340, "score": 9}]}',
            '{"clips": [{"start": 500, "end": 540, "score": 7}]}',
        ]
    )

    class Backend:
        name = "fake"

        def complete(self, prompt):
            return next(answers, '{"clips": []}')

    clips = find_clips(segments(60), settings, duration=600, backend=Backend(), log=lambda *_: None)
    assert [c.score for c in clips] == [9, 7]
