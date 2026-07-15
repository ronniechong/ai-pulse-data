"""Model-slug-prefix -> provider identity mapping.

Explicit table rather than parsing the raw prefix, so slug renames/drift and
human-readable display names are curated by hand instead of assumed stable.
Unmapped prefixes fail open (see resolve_provider) rather than blocking a run.
"""

import sys

# raw prefix (everything before the first "/" in model_permaslug) -> display name
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
