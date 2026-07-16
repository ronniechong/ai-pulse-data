import json
from datetime import UTC, datetime

from aipulse.config import DATA_DIR, LATEST_DIR, MANIFEST_PATH, SCHEMA_VERSION

SOURCE_FILENAMES = {
    "rankings": "rankings.json",
    "apps": "apps.json",
    "hf_trending": "hf-trending.json",
    "sdk_geo": "sdk-geo.json",
    "geo_adoption": "geo-adoption.json",
    "geo_regions": "geo-regions.json",
    "occupations": "occupations.json",
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
