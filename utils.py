from datetime import datetime, timedelta
from pathlib import Path

def should_update_ytdlp(update_timestamp_file: Path) -> bool:
    """Check if yt-dlp should be updated (once per day)"""
    if not update_timestamp_file.exists():
        return True
    try:
        last_update: datetime = datetime.fromisoformat(update_timestamp_file.read_text().strip())
        return datetime.now() - last_update > timedelta(days=1)
    except Exception:
        # If the timestamp file is corrupted or unreadable, force an update
        return True
