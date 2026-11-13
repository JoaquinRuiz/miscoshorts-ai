import pytest

from miscoshorts.timeparse import format_time, parse_range, parse_time


@pytest.mark.parametrize(
    ("text", "seconds"),
    [
        ("120", 120),
        ("120.5", 120.5),
        ("120,5", 120.5),
        ("120.5s", 120.5),
        (" 120 S ", 120),
        ("2:00", 120),
        ("1:02:03", 3723),
        ("1:02:03.5", 3723.5),
        ("**155.0**", 155),
        ("[42]", 42),
        (90, 90),
        (12.5, 12.5),
    ],
)
def test_parse_time(text, seconds):
    assert parse_time(text) == pytest.approx(seconds)


@pytest.mark.parametrize("bad", ["", "abc", "1:2:3:4", "-5", "12.5.3", -1])
def test_parse_time_rejects(bad):
    with pytest.raises(ValueError):
        parse_time(bad)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("120-140", (120, 140)),
        ("2:00 - 2:20", (120, 140)),
        ("2:00–2:20", (120, 140)),
        ("2:00 a 2:20", (120, 140)),
        ("90 to 120.5", (90, 120.5)),
    ],
)
def test_parse_range(text, expected):
    assert parse_range(text) == pytest.approx(expected)


@pytest.mark.parametrize("bad", ["120", "-140", "120-", "a-b"])
def test_parse_range_rejects(bad):
    with pytest.raises(ValueError):
        parse_range(bad)


def test_format_time():
    assert format_time(65.25) == "1:05.2"
    assert format_time(3723) == "1:02:03.0"
