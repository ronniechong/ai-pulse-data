"""Data-quality gates. Every gate returns a list of violation strings — empty
means pass. Any violation triggers the same "skip source, keep last good,
alert" path as a schema failure; see DATA_QUALITY.md for rationale.
"""

from aipulse.config import QUALITY_ROW_BOUNDS, TOP1_TOKEN_SHARE_MAX, TOP1_TOKEN_SHARE_MIN

_ROW_COUNT_MAX_DROP_RATIO = 0.5


def _row_count(source_key: str, normalized: dict) -> int:
    if source_key == "rankings":
        return len(normalized["models"])
    if source_key == "apps":
        return len(normalized["apps"])
    if source_key == "hf_trending":
        return len(normalized["models"])
    if source_key == "sdk_geo":
        return sum(len(p["countries"]) for p in normalized["packages"].values())
    raise ValueError(f"unknown source_key {source_key!r}")


def check_row_count_bounds(source_key: str, normalized: dict) -> list[str]:
    count = _row_count(source_key, normalized)
    lo, hi = QUALITY_ROW_BOUNDS[source_key]
    if not (lo <= count <= hi):
        return [f"{source_key}: row count {count} outside plausible bounds [{lo}, {hi}]"]
    return []


def check_row_count_vs_previous(
    source_key: str, normalized: dict, previous: dict | None
) -> list[str]:
    if previous is None:
        return []
    current = _row_count(source_key, normalized)
    prior = _row_count(source_key, previous)
    if prior == 0:
        return []
    if current < prior * (1 - _ROW_COUNT_MAX_DROP_RATIO):
        return [
            f"{source_key}: row count dropped from {prior} to {current} "
            f"(more than {_ROW_COUNT_MAX_DROP_RATIO:.0%} decline vs previous run)"
        ]
    return []


def check_nulls(source_key: str, normalized: dict) -> list[str]:
    violations = []
    if source_key == "rankings":
        for m in normalized["models"]:
            if not m["model"] or m["total_tokens"] < 0:
                violations.append(f"rankings: invalid row {m!r}")
    elif source_key == "apps":
        for a in normalized["apps"]:
            if not a["app_name"] or a["total_tokens"] < 0:
                violations.append(f"apps: invalid row {a!r}")
    elif source_key == "hf_trending":
        for m in normalized["models"]:
            if not m["id"] or m["downloads"] < 0:
                violations.append(f"hf_trending: invalid row {m!r}")
    elif source_key == "sdk_geo":
        for package, data in normalized["packages"].items():
            for c in data["countries"]:
                if not c["country_code"] or c["downloads"] < 0:
                    violations.append(f"sdk_geo/{package}: invalid row {c!r}")
    return violations


def check_top1_token_share(normalized: dict) -> list[str]:
    """Only meaningful for rankings — catches a single model implausibly dominating
    (data glitch) or the top row being suspiciously small (aggregation bug)."""
    models = [m for m in normalized["models"] if m["model"] != "other"]
    if not models:
        return []
    share = models[0]["token_share"]
    if not (TOP1_TOKEN_SHARE_MIN <= share <= TOP1_TOKEN_SHARE_MAX):
        return [
            f"rankings: top-1 model token share {share:.2%} outside plausible band "
            f"[{TOP1_TOKEN_SHARE_MIN:.0%}, {TOP1_TOKEN_SHARE_MAX:.0%}]"
        ]
    return []


def evaluate(source_key: str, normalized: dict, previous: dict | None) -> list[str]:
    violations = [
        *check_row_count_bounds(source_key, normalized),
        *check_row_count_vs_previous(source_key, normalized, previous),
        *check_nulls(source_key, normalized),
    ]
    if source_key == "rankings":
        violations += check_top1_token_share(normalized)
    return violations
