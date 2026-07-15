import json
import re
from datetime import UTC, datetime

from aipulse.config import DATA_DIR, LATEST_DIR, MANIFEST_PATH, SCHEMA_VERSION

_DATED_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

SOURCE_FILENAMES = {
    "rankings": "rankings.json",
    "apps": "apps.json",
    "hf_trending": "hf-trending.json",
    "sdk_geo": "sdk-geo.json",
    "geo_adoption": "geo-adoption.json",
    "facts": "facts.json",
    "commentary": "commentary.json",
}


def load_previous(source_key: str) -> dict | None:
    path = LATEST_DIR / SOURCE_FILENAMES[source_key]
    if not path.exists():
        return None
    return json.loads(path.read_text())


def write_source(source_key: str, normalized: dict, date_str: str) -> None:
    filename = SOURCE_FILENAMES[source_key]
    dated_dir = DATA_DIR / date_str
    dated_dir.mkdir(parents=True, exist_ok=True)
    LATEST_DIR.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(normalized, indent=2, sort_keys=False) + "\n"
    (dated_dir / filename).write_text(payload)
    (LATEST_DIR / filename).write_text(payload)


def load_history(source_key: str, *, up_to_date: str | None = None) -> list[tuple[str, dict]]:
    """All committed dated snapshots for a source, oldest first, as (date_str, normalized).
    Skips dates with no file for this source (e.g. a degraded run). `up_to_date` is
    inclusive, so the caller can exclude "today" when diffing today against history."""
    if not DATA_DIR.exists():
        return []
    filename = SOURCE_FILENAMES[source_key]
    out = []
    for entry in sorted(DATA_DIR.iterdir()):
        if not entry.is_dir() or not _DATED_DIR_RE.match(entry.name):
            continue
        if up_to_date is not None and entry.name > up_to_date:
            continue
        path = entry / filename
        if path.exists():
            out.append((entry.name, json.loads(path.read_text())))
    return out


def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        return {"sources": {}}
    return json.loads(MANIFEST_PATH.read_text())


def write_manifest(date_str: str, source_statuses: dict[str, dict]) -> None:
    manifest = load_manifest()
    sources = manifest.get("sources", {})
    for source_key, status in source_statuses.items():
        sources[source_key] = status

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "data_version": date_str,
        "schema_version": SCHEMA_VERSION,
        "sources": sources,
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
