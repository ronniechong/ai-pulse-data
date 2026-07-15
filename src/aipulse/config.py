import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
LATEST_DIR = DATA_DIR / "latest"
MANIFEST_PATH = DATA_DIR / "manifest.json"

SCHEMA_VERSION = 1

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
HF_TOKEN = os.environ.get("HF_TOKEN", "")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")

OPENROUTER_RANKINGS_URL = "https://openrouter.ai/api/v1/datasets/rankings-daily"
OPENROUTER_APP_RANKINGS_URL = "https://openrouter.ai/api/v1/datasets/app-rankings"
HF_MODELS_URL = "https://huggingface.co/api/models"
CLICKHOUSE_URL = "https://sql-clickhouse.clickhouse.com"
NTFY_URL = "https://ntfy.sh"

HF_TRENDING_LIMIT = 50

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
