"""Deterministic diff engine over rankings history -> facts.json.

No LLM here. Every number in commentary.py's prompt must trace back to a
field this module computed, so entity/number validation downstream has
something concrete to check against. See work-docs M2 design spec for the
definitions this implements (new entrant/dropout, records, provider share).
"""

from datetime import UTC, datetime

from aipulse.providers import OTHER_PROVIDER_KEY, resolve_provider

# Tolerance windows for locating a "7 days ago" / "30 days ago" comparison
# snapshot when a day was skipped (degraded source) — closest date within
# the window wins; outside the window the delta is null, not guessed.
_WINDOW_7D = (5, 9)
_WINDOW_30D = (26, 34)


def _index_by_model(snapshot: dict) -> dict[str, dict]:
    return {m["model"]: m for m in snapshot["models"]}


def _find_comparison(history: list[tuple[str, dict]], today_date: str, lo_days: int, hi_days: int):
    """Nearest snapshot whose date falls `lo_days`..`hi_days` before today_date."""
    today_d = datetime.fromisoformat(today_date).date()
    best = None
    best_diff = None
    for date_str, snapshot in history:
        d = datetime.fromisoformat(date_str).date()
        age = (today_d - d).days
        if lo_days <= age <= hi_days:
            diff = abs(age - (lo_days + hi_days) / 2)
            if best is None or diff < best_diff:
                best, best_diff = snapshot, diff
    return best


def _rank_and_share_delta(today_row: dict, compare_row: dict | None) -> tuple[int | None, float | None]:
    if compare_row is None:
        return None, None
    rank_delta = compare_row["rank"] - today_row["rank"]  # positive = moved up
    share_delta = round(today_row["token_share"] - compare_row["token_share"], 6)
    return rank_delta, share_delta


def _compute_movers(today: dict, yesterday: dict | None, d7: dict | None, d30: dict | None) -> list[dict]:
    yesterday_idx = _index_by_model(yesterday) if yesterday else {}
    d7_idx = _index_by_model(d7) if d7 else {}
    d30_idx = _index_by_model(d30) if d30 else {}

    movers = []
    for row in today["models"]:
        model = row["model"]
        if model == OTHER_PROVIDER_KEY:
            continue
        rank_delta_1d, share_delta_1d = _rank_and_share_delta(row, yesterday_idx.get(model))
        rank_delta_7d, share_delta_7d = _rank_and_share_delta(row, d7_idx.get(model))
        rank_delta_30d, share_delta_30d = _rank_and_share_delta(row, d30_idx.get(model))
        movers.append(
            {
                "model": model,
                "provider": resolve_provider(model),
                "rank_today": row["rank"],
                "token_share_today": row["token_share"],
                "rank_delta_1d": rank_delta_1d,
                "token_share_delta_1d": share_delta_1d,
                "rank_delta_7d": rank_delta_7d,
                "token_share_delta_7d": share_delta_7d,
                "rank_delta_30d": rank_delta_30d,
                "token_share_delta_30d": share_delta_30d,
            }
        )
    return movers


def _compute_entrants_and_dropouts(today: dict, yesterday: dict | None) -> tuple[list[dict], list[dict]]:
    if yesterday is None:
        return [], []
    today_models = {m["model"] for m in today["models"]}
    yesterday_models = {m["model"] for m in yesterday["models"]}
    yesterday_idx = _index_by_model(yesterday)
    today_idx = _index_by_model(today)

    entrants = [
        {
            "model": m,
            "provider": resolve_provider(m),
            "rank": today_idx[m]["rank"],
            "token_share": today_idx[m]["token_share"],
        }
        for m in today_models - yesterday_models
        if m != OTHER_PROVIDER_KEY
    ]
    dropouts = [
        {
            "model": m,
            "provider": resolve_provider(m),
            "last_rank": yesterday_idx[m]["rank"],
            "last_token_share": yesterday_idx[m]["token_share"],
        }
        for m in yesterday_models - today_models
        if m != OTHER_PROVIDER_KEY
    ]
    entrants.sort(key=lambda e: e["rank"])
    dropouts.sort(key=lambda d: d["last_rank"])
    return entrants, dropouts


def _compute_records(today: dict, prior_history: list[tuple[str, dict]]) -> list[dict]:
    """prior_history must exclude today. Empty prior_history => no records possible."""
    if not prior_history:
        return []

    prior_max_share: dict[str, float] = {}
    ever_rank1: set[str] = set()
    for _date_str, snapshot in prior_history:
        for row in snapshot["models"]:
            if row["model"] == OTHER_PROVIDER_KEY:
                continue
            prior_max_share[row["model"]] = max(
                prior_max_share.get(row["model"], 0.0), row["token_share"]
            )
            if row["rank"] == 1:
                ever_rank1.add(row["model"])

    records = []
    for row in today["models"]:
        model = row["model"]
        if model == OTHER_PROVIDER_KEY:
            continue
        prior_max = prior_max_share.get(model)
        if prior_max is not None and row["token_share"] > prior_max:
            records.append(
                {
                    "type": "all_time_token_share",
                    "model": model,
                    "provider": resolve_provider(model),
                    "value": row["token_share"],
                }
            )
        if row["rank"] == 1 and model not in ever_rank1:
            records.append(
                {
                    "type": "first_time_rank1",
                    "model": model,
                    "provider": resolve_provider(model),
                    "value": row["token_share"],
                }
            )
    return records


def _compute_provider_share(
    today: dict, yesterday: dict | None, d7: dict | None, d30: dict | None
) -> list[dict]:
    def by_provider(snapshot: dict | None) -> dict[str, float]:
        if snapshot is None:
            return {}
        totals: dict[str, float] = {}
        for row in snapshot["models"]:
            if row["model"] == OTHER_PROVIDER_KEY:
                continue
            provider = resolve_provider(row["model"])
            totals[provider] = totals.get(provider, 0.0) + row["token_share"]
        return totals

    today_shares = by_provider(today)
    yesterday_shares = by_provider(yesterday)
    d7_shares = by_provider(d7)
    d30_shares = by_provider(d30)

    def delta(provider: str, comparison: dict[str, float]) -> float | None:
        if provider not in comparison:
            return None
        return round(today_shares[provider] - comparison[provider], 6)

    return [
        {
            "provider": provider,
            "token_share_today": round(share, 6),
            "delta_1d": delta(provider, yesterday_shares),
            "delta_7d": delta(provider, d7_shares),
            "delta_30d": delta(provider, d30_shares),
        }
        for provider, share in sorted(today_shares.items(), key=lambda kv: -kv[1])
    ]


def compute_facts(history: list[tuple[str, dict]]) -> dict:
    """history: (date_str, normalized rankings dict) ascending by date, with the
    last entry being "today". Returns the facts.json payload (see M2 design spec)."""
    if not history:
        raise ValueError("compute_facts requires at least today's snapshot")

    today_date, today = history[-1]
    prior_history = history[:-1]

    yesterday = _find_comparison(prior_history, today_date, 1, 1)
    d7 = _find_comparison(prior_history, today_date, *_WINDOW_7D)
    d30 = _find_comparison(prior_history, today_date, *_WINDOW_30D)

    entrants, dropouts = _compute_entrants_and_dropouts(today, yesterday)

    return {
        "date": today_date,
        "generated_at": datetime.now(UTC).isoformat(),
        "rankings": {
            "movers": _compute_movers(today, yesterday, d7, d30),
            "new_entrants": entrants,
            "dropouts": dropouts,
            "records": _compute_records(today, prior_history),
            "provider_share": _compute_provider_share(today, yesterday, d7, d30),
        },
    }


def _threshold_hit(facts: dict) -> str:
    """Rule-based tone — see M2 design spec for the thresholds and rationale."""
    rankings = facts["rankings"]
    if rankings["records"]:
        return "big_day"
    if any(abs(p["delta_1d"] or 0) >= 0.03 for p in rankings["provider_share"]):
        return "big_day"
    if rankings["new_entrants"] or rankings["dropouts"]:
        return "notable"
    if any(abs(m["rank_delta_1d"] or 0) >= 10 for m in rankings["movers"]):
        return "notable"
    if any(abs(m["token_share_delta_1d"] or 0) >= 0.01 for m in rankings["movers"]):
        return "notable"
    return "quiet"


def compute_tone(facts: dict) -> str:
    return _threshold_hit(facts)
