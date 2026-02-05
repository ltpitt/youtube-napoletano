import pytest
from downloader import parse_progress

def test_parse_progress_full():
    line = "[download] 42.0% of 10.00MiB at 2.00MiB/s ETA 00:10"
    result = parse_progress(line)
    assert result == {
        "percent": "42.0",
        "size": "10.00MiB",
        "speed": "2.00MiB/s",
        "eta": "00:10",
    }

def test_parse_progress_simple():
    line = "[download] 10.0% of 1.00MiB"
    result = parse_progress(line)
    assert result == {
        "percent": "10.0",
        "size": "1.00MiB",
        "speed": "N/A",
        "eta": "N/A",
    }

def test_parse_progress_none():
    line = "[other] something else"
    assert parse_progress(line) is None
