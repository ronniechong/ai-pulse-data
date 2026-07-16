"""Shared helpers for pulling releases from the Anthropic Economic Index
dataset on Hugging Face (huggingface.co/datasets/Anthropic/EconomicIndex).
Used by the quarterly-manual ingest scripts (geo-adoption, occupations) —
see scripts/ingest_geo_adoption.py and scripts/ingest_occupations.py."""

import re
import tempfile
from pathlib import Path

import requests

HF_DATASET = "Anthropic/EconomicIndex"
HF_API = f"https://huggingface.co/api/datasets/{HF_DATASET}/tree/main"
HF_RESOLVE = f"https://huggingface.co/datasets/{HF_DATASET}/resolve/main"
RELEASE_RE = re.compile(r"^release_\d{4}_\d{2}_\d{2}$")


def find_latest_release() -> str:
    resp = requests.get(HF_API, timeout=30)
    resp.raise_for_status()
    entries = resp.json()
    releases = sorted(
        e["path"].rsplit("/", 1)[-1]
        for e in entries
        if e["type"] == "directory" and RELEASE_RE.match(e["path"])
    )
    if not releases:
        raise RuntimeError(f"No release_YYYY_MM_DD folders found in {HF_DATASET}")
    return releases[-1]


def find_claude_ai_csv(release: str) -> str:
    resp = requests.get(f"{HF_API}/{release}/data", timeout=30)
    resp.raise_for_status()
    for entry in resp.json():
        name = entry["path"].rsplit("/", 1)[-1]
        if name.startswith("aei_claude_ai_") and name.endswith(".csv"):
            return entry["path"]
    raise RuntimeError(f"No aei_claude_ai_*.csv found under {release}/data")


def download(path: str) -> Path:
    url = f"{HF_RESOLVE}/{path}"
    tmp = Path(tempfile.mkstemp(suffix=".csv")[1])
    with requests.get(url, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        with tmp.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
    return tmp
