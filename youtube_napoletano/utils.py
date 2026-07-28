from datetime import datetime, timedelta, timezone
from pathlib import Path


def should_update_ytdlp(update_timestamp_file: Path) -> bool:
    """Check if yt-dlp should be updated (once per day)"""
    if not update_timestamp_file.exists():
        return True
    try:
        last_update: datetime = datetime.fromisoformat(
            update_timestamp_file.read_text().strip()
        )
        if last_update.tzinfo is None:
            last_update = last_update.replace(tzinfo=timezone.utc)
        return datetime.now(tz=timezone.utc) - last_update > timedelta(days=1)
    except (ValueError, OSError):
        # If the timestamp file is corrupted or unreadable, force an update
        return True
