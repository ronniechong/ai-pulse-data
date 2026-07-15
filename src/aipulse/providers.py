"""Model-slug-prefix -> provider identity mapping.

Explicit table rather than parsing the raw prefix, so slug renames/drift and
human-readable display names are curated by hand instead of assumed stable.
Unmapped prefixes fail open (see resolve_provider) rather than blocking a run.
"""

import sys

# raw prefix (everything before the first "/" in model_permaslug) -> display name.
# Seeded from the M2.5 backfill's full 2025-01-01..2026-07-14 history (40
# distinct prefixes), not just a single day's top-51 — a single day misses
# smaller/older providers entirely.
PROVIDER_MAP: dict[str, str] = {
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "google": "Google",
    "deepseek": "DeepSeek",
    "mistralai": "Mistral AI",
    "x-ai": "xAI",
    "qwen": "Qwen",
    "moonshotai": "Moonshot AI",
    "z-ai": "Zhipu AI",
    "minimax": "MiniMax",
    "nvidia": "NVIDIA",
    "tencent": "Tencent",
    "xiaomi": "Xiaomi",
    "stepfun": "StepFun",
    "poolside": "Poolside",
    "alibaba": "Alibaba",
    "amazon": "Amazon",
    "anthracite-org": "Anthracite",
    "arcee-ai": "Arcee AI",
    "baai": "BAAI",
    "bytedance-seed": "ByteDance",
    "cognitivecomputations": "Cognitive Computations",
    "cohere": "Cohere",
    "gryphe": "Gryphe",
    "inclusionai": "InclusionAI",
    "infermatic": "Infermatic",
    "intfloat": "intfloat",
    "kwaipilot": "Kwaipilot",
    "liquid": "Liquid AI",
    "meta-llama": "Meta",
    "microsoft": "Microsoft",
    "neversleep": "NeverSleep",
    "nex-agi": "Nex AGI",
    "nousresearch": "Nous Research",
    "openchat": "OpenChat",
    "openrouter": "OpenRouter",
    "perplexity": "Perplexity",
    "sao10k": "Sao10K",
    "sentence-transformers": "Sentence Transformers",
    "thedrummer": "TheDrummer",
    "tngtech": "TNG Technology Consulting",
}

# Pseudo-provider for OpenRouter's aggregate "other" bucket (no "/" in the slug).
# Excluded from provider-share leaderboard framing — see facts.py.
OTHER_PROVIDER_KEY = "other"


def resolve_provider(model_permaslug: str) -> str:
    """Returns a display-name provider for a model_permaslug. Fails open: an
    unmapped prefix is used verbatim (as both id and display name) with a
    warning, so a new/renamed provider never blocks a pipeline run."""
    if "/" not in model_permaslug:
        return OTHER_PROVIDER_KEY
    prefix = model_permaslug.split("/", 1)[0]
    provider = PROVIDER_MAP.get(prefix)
    if provider is None:
        print(f"[providers] unmapped prefix {prefix!r} (model {model_permaslug!r}) — add to PROVIDER_MAP", file=sys.stderr)
        return prefix
    return provider
