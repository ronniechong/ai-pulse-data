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
COMMENTARY_PROMPT_VERSION = "commentary-v1"
COMMENTARY_MAX_RETRIES = 1  # 1 retry on validation failure, then template fallback

SPEND_LEDGER_PATH = REPO_ROOT / "spend-ledger.json"
SPEND_CAP_USD_PER_MONTH = 2.0

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
