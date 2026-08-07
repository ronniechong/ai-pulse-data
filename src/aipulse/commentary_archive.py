"""Full-history index behind the ai-pulse-web commentary archive page.

Unlike the fetched-data rollups in history_rollup.py, this has no external
source to merge a window from — commentary.json is already written into
every dated data/YYYY-MM-DD/ folder by run_facts_and_commentary. This just
rescans every folder and flattens what's already on disk into one file, so
the archive page can page through history with a single fetch instead of
one request per day.
"""

import json
import re
from datetime import UTC, datetime

from aipulse.config import DATA_DIR, LATEST_DIR

_DATE_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def build_archive_index() -> list[dict]:
    """Full rescan every run (cheap: one small JSON read per day) rather than
    an incremental merge — self-heals automatically if a day's commentary.json
    is ever corrected after the fact, with no separate merge-state to drift
    out of sync."""
    entries = []
    for entry in DATA_DIR.iterdir():
        if not entry.is_dir() or not _DATE_DIR_RE.match(entry.name):
            continue
        commentary_path = entry / "commentary.json"
        if not commentary_path.exists():
            continue
        commentary = json.loads(commentary_path.read_text())
        entries.append(
            {
                "date": entry.name,
                "headline": commentary.get("headline"),
                "summary": commentary.get("summary"),
                "highlights": commentary.get("highlights", []),
                "tone": commentary.get("tone"),
                # Absent on days written before the source field existed
                # (see schemas.CommentaryOutput) — the archive UI must treat
                # this as "unknown", not assume every day carries it.
                "source": commentary.get("source"),
            }
        )
    return sorted(entries, key=lambda e: e["date"], reverse=True)


def save_archive_index(entries: list[dict]) -> None:
    LATEST_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"generated_at": datetime.now(UTC).isoformat(), "entries": entries}
    (LATEST_DIR / "commentary-archive.json").write_text(json.dumps(payload, indent=2) + "\n")
