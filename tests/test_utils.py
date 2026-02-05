import pytest
from pathlib import Path
from datetime import datetime, timedelta
from utils import should_update_ytdlp

def test_should_update_ytdlp_new_file(tmp_path):
    file = tmp_path / "timestamp.txt"
    assert should_update_ytdlp(file) is True

def test_should_update_ytdlp_old_file(tmp_path):
    file = tmp_path / "timestamp.txt"
    file.write_text((datetime.now() - timedelta(days=2)).isoformat())
    assert should_update_ytdlp(file) is True

def test_should_update_ytdlp_recent_file(tmp_path):
    file = tmp_path / "timestamp.txt"
    file.write_text(datetime.now().isoformat())
    assert should_update_ytdlp(file) is False

def test_should_update_ytdlp_corrupt_file(tmp_path):
    file = tmp_path / "timestamp.txt"
    file.write_text("not-a-date")
    assert should_update_ytdlp(file) is True
