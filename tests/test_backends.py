"""OpenAI-compatible backend: structured output with fallbacks (no network)."""

import pytest

openai = pytest.importorskip("openai")
httpx = pytest.importorskip("httpx")

from miscoshorts.config import Settings  # noqa: E402
from miscoshorts.llm import OpenAIBackend, clips_schema  # noqa: E402


def test_schema_requires_every_field_in_strict_mode():
    schema = clips_schema()
    item = schema["properties"]["clips"]["items"]
    assert set(item["required"]) == set(item["properties"])
    assert item["additionalProperties"] is False
    assert "additionalProperties" not in clips_schema(strict=False)


class FakeCompletions:
    def __init__(self, reject):
        self.reject = reject
        self.formats = []

    def create(self, **kwargs):
        fmt = kwargs.get("response_format")
        self.formats.append(fmt["type"] if fmt else None)
        if fmt and fmt["type"] in self.reject:
            request = httpx.Request("POST", "http://test/v1/chat/completions")
            raise openai.BadRequestError(
                "unsupported", response=httpx.Response(400, request=request), body=None
            )
        message = type("M", (), {"content": '{"clips": []}'})
        return type("R", (), {"choices": [type("C", (), {"message": message})]})


@pytest.mark.parametrize(
    ("reject", "expected"),
    [
        (set(), ["json_schema"]),
        ({"json_schema"}, ["json_schema", "json_object"]),
        ({"json_schema", "json_object"}, ["json_schema", "json_object", None]),
    ],
)
def test_falls_back_and_remembers(reject, expected):
    backend = OpenAIBackend(Settings(backend="openai"))
    fake = FakeCompletions(reject)
    backend._client = type("Client", (), {"chat": type("Chat", (), {"completions": fake})})
    assert backend.complete("hola") == '{"clips": []}'
    assert fake.formats == expected
    fake.formats.clear()
    backend.complete("otra vez")
    assert fake.formats == expected[-1:]  # the working format is remembered
