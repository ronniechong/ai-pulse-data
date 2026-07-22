import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
LATEST_DIR = DATA_DIR / "latest"
MANIFEST_PATH = DATA_DIR / "manifest.json"

SCHEMA_VERSION = 2  # bumped for M2.5: rankings-history.json / sdk-geo-history.json rollups

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
HF_TOKEN = os.environ.get("HF_TOKEN", "")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
LANGFUSE_PUBLIC_KEY = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.environ.get("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")

# "true"/"1"/"yes" (case-insensitive) enables the commentary step; anything
# else (including unset) means facts-only, template-free-day skip.
COMMENTARY_ENABLED = os.environ.get("COMMENTARY_ENABLED", "").strip().lower() in ("true", "1", "yes")

OPENROUTER_RANKINGS_URL = "https://openrouter.ai/api/v1/datasets/rankings-daily"
OPENROUTER_APP_RANKINGS_URL = "https://openrouter.ai/api/v1/datasets/app-rankings"
OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
HF_MODELS_URL = "https://huggingface.co/api/models"
CLICKHOUSE_URL = "https://sql-clickhouse.clickhouse.com"
NTFY_URL = "https://ntfy.sh"
LANGFUSE_INGESTION_PATH = "/api/public/ingestion"

COMMENTARY_MODEL = "~anthropic/claude-haiku-latest"  # OpenRouter's auto-updating alias, avoids tracking dated slugs
COMMENTARY_PROMPT_VERSION = "commentary-v2"
COMMENTARY_MAX_RETRIES = 1  # 1 retry on validation failure, then template fallback

SPEND_LEDGER_PATH = REPO_ROOT / "spend-ledger.json"
SPEND_CAP_USD_PER_MONTH = 2.0

# History rollups (data/latest/ only — never a dated data/YYYY-MM-DD/ copy;
# these are cumulative rollups, not daily snapshots, and must stay out of the
# burn-in provenance story). rankings, sdk_geo, and rankings_daily_totals are
# all fed by a one-off backfill script AND the daily pipeline. sdk-geo-history
# is large (56MB+, ~300k rows) and never served to the client directly —
# sdk_geo_trend.py derives a small per-region/per-package daily summary from
# it instead. rankings_daily_totals stays tiny by design (one row per day,
# not per model) — served to the client as-is, same as rankings-history.
ROLLUP_FILENAMES = {
    "rankings": "rankings-history.json",
    "sdk_geo": "sdk-geo-history.json",
    "rankings_daily_totals": "rankings-totals-history.json",
}

# Trailing window (days) re-fetched from ClickPy into sdk-geo-history on every
# pipeline run — generous overlap so late-arriving/corrected ClickPy data
# self-heals the same way rankings-history's window fetch does, ending
# yesterday since "today" is never a complete day in ClickPy either.
SDK_GEO_HISTORY_WINDOW_DAYS = 30

# OpenRouter's rankings-daily data floor (confirmed live 2026-07-16 via the
# API's own error message). Max span per request is 366 days.
RANKINGS_HISTORY_FLOOR = "2025-01-01"
OPENROUTER_MAX_WINDOW_DAYS = 366

# The day before the real CI pipeline's first production run (2026-07-15) —
# the backfill script's window ends the day before this so there's no
# overlap/gap with pipeline-sourced rollup rows.
BACKFILL_END_DATE = "2026-07-14"

HF_TRENDING_LIMIT = 50

# App-rankings category/subcategory tagging (M2.6). Values confirmed live
# 2026-07-16 via the API's own ZodError enum on an invalid value — the
# design brief's "cli-agent" guess turned out to be a *subcategory* of the
# "coding" *category*, not a category itself; mismatched category+subcategory
# pairs 400. Each filtered call returns its own top-50, tagged onto whichever
# app_ids appear in it — most apps in the base top-50 won't match any slice,
# which is expected (fail open, not an error).
APP_RANKING_CATEGORIES = ["coding", "creative", "productivity", "entertainment"]
APP_RANKING_TAG_SUBCATEGORIES = ["cli-agent"]  # only the one the M3 design needs; more available later

# SDK download tracking: PyPI package name -> provider label
SDK_PACKAGES = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google-generativeai": "Google",
    "ollama": "Ollama",
    "mistralai": "Mistral AI",
}

# Row-count sanity bands: source -> (min_rows, max_rows)
QUALITY_ROW_BOUNDS = {
    "rankings": (40, 60),  # top-50 + 'other' row, some slack
    "apps": (10, 500),
    "hf_trending": (HF_TRENDING_LIMIT - 5, HF_TRENDING_LIMIT + 5),
    "sdk_geo": (len(SDK_PACKAGES), len(SDK_PACKAGES) * 250),  # up to ~250 countries/pkg
}

# Plausibility band for the top-1 model's share of total top-50 tokens
TOP1_TOKEN_SHARE_MIN = 0.02
TOP1_TOKEN_SHARE_MAX = 0.60
