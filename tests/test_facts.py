from aipulse.facts import compute_facts, compute_tone


def _snapshot(date: str, models: list[dict]) -> dict:
    return {"generated_at": f"{date}T00:00:00+00:00", "date": date, "models": models}


def _row(rank: int, model: str, token_share: float) -> dict:
    return {"rank": rank, "model": model, "total_tokens": int(token_share * 10**12), "token_share": token_share}


def test_day_one_has_no_deltas_and_no_records():
    today = _snapshot("2026-07-15", [_row(1, "anthropic/claude", 0.3), _row(2, "openai/gpt", 0.2)])
    facts = compute_facts([("2026-07-15", today)])

    assert facts["rankings"]["records"] == []
    assert facts["rankings"]["new_entrants"] == []
    assert facts["rankings"]["dropouts"] == []
    movers = {m["model"]: m for m in facts["rankings"]["movers"]}
    assert movers["anthropic/claude"]["rank_delta_1d"] is None
    assert movers["anthropic/claude"]["token_share_delta_1d"] is None


def test_mover_rank_and_share_deltas_vs_yesterday():
    yesterday = _snapshot("2026-07-15", [_row(1, "anthropic/claude", 0.30), _row(2, "openai/gpt", 0.20)])
    today = _snapshot("2026-07-16", [_row(1, "openai/gpt", 0.28), _row(2, "anthropic/claude", 0.25)])
    facts = compute_facts([("2026-07-15", yesterday), ("2026-07-16", today)])

    movers = {m["model"]: m for m in facts["rankings"]["movers"]}
    assert movers["openai/gpt"]["rank_delta_1d"] == 1  # moved from rank 2 to rank 1
    assert movers["openai/gpt"]["token_share_delta_1d"] == round(0.28 - 0.20, 6)
    assert movers["anthropic/claude"]["rank_delta_1d"] == -1  # moved from rank 1 to rank 2
    assert movers["anthropic/claude"]["token_share_delta_1d"] == round(0.25 - 0.30, 6)


def test_new_entrant_and_dropout():
    yesterday = _snapshot("2026-07-15", [_row(1, "anthropic/claude", 0.30), _row(2, "openai/gpt", 0.20)])
    today = _snapshot("2026-07-16", [_row(1, "anthropic/claude", 0.30), _row(2, "google/gemini", 0.20)])
    facts = compute_facts([("2026-07-15", yesterday), ("2026-07-16", today)])

    assert [e["model"] for e in facts["rankings"]["new_entrants"]] == ["google/gemini"]
    assert [d["model"] for d in facts["rankings"]["dropouts"]] == ["openai/gpt"]


def test_other_bucket_excluded_from_entrants_and_movers():
    yesterday = _snapshot("2026-07-15", [_row(1, "anthropic/claude", 0.30), _row(2, "other", 0.10)])
    today = _snapshot("2026-07-16", [_row(1, "anthropic/claude", 0.30)])
    facts = compute_facts([("2026-07-15", yesterday), ("2026-07-16", today)])

    assert facts["rankings"]["dropouts"] == []
    assert all(m["model"] != "other" for m in facts["rankings"]["movers"])


def test_record_all_time_token_share_high():
    day1 = _snapshot("2026-07-14", [_row(1, "anthropic/claude", 0.20)])
    day2 = _snapshot("2026-07-15", [_row(1, "anthropic/claude", 0.25)])
    day3 = _snapshot("2026-07-16", [_row(1, "anthropic/claude", 0.35)])
    facts = compute_facts([("2026-07-14", day1), ("2026-07-15", day2), ("2026-07-16", day3)])

    records = facts["rankings"]["records"]
    assert any(r["type"] == "all_time_token_share" and r["model"] == "anthropic/claude" for r in records)


def test_record_first_time_rank1():
    day1 = _snapshot("2026-07-14", [_row(1, "anthropic/claude", 0.30), _row(2, "openai/gpt", 0.20)])
    day2 = _snapshot("2026-07-15", [_row(1, "openai/gpt", 0.32), _row(2, "anthropic/claude", 0.28)])
    facts = compute_facts([("2026-07-14", day1), ("2026-07-15", day2)])

    records = facts["rankings"]["records"]
    assert any(r["type"] == "first_time_rank1" and r["model"] == "openai/gpt" for r in records)
    # anthropic/claude was already rank 1 before, so its drop to rank 2 isn't a "first time" anything
    assert not any(r["model"] == "anthropic/claude" and r["type"] == "first_time_rank1" for r in records)


def test_no_repeat_record_once_already_achieved():
    day1 = _snapshot("2026-07-14", [_row(1, "anthropic/claude", 0.30)])
    day2 = _snapshot("2026-07-15", [_row(1, "anthropic/claude", 0.30)])  # same share, still rank 1
    facts = compute_facts([("2026-07-14", day1), ("2026-07-15", day2)])

    assert facts["rankings"]["records"] == []


def test_provider_share_aggregates_multiple_models_per_provider():
    today = _snapshot(
        "2026-07-16",
        [
            _row(1, "anthropic/claude-opus", 0.20),
            _row(2, "anthropic/claude-sonnet", 0.10),
            _row(3, "openai/gpt", 0.15),
        ],
    )
    facts = compute_facts([("2026-07-16", today)])

    shares = {p["provider"]: p["token_share_today"] for p in facts["rankings"]["provider_share"]}
    assert shares["Anthropic"] == round(0.30, 6)
    assert shares["OpenAI"] == round(0.15, 6)


def test_7d_and_30d_use_nearest_snapshot_within_tolerance():
    d0 = _snapshot("2026-06-16", [_row(1, "anthropic/claude", 0.10)])  # ~30d before
    d1 = _snapshot("2026-07-09", [_row(1, "anthropic/claude", 0.20)])  # ~7d before
    d2 = _snapshot("2026-07-16", [_row(1, "anthropic/claude", 0.30)])  # today
    facts = compute_facts([("2026-06-16", d0), ("2026-07-09", d1), ("2026-07-16", d2)])

    movers = {m["model"]: m for m in facts["rankings"]["movers"]}
    assert movers["anthropic/claude"]["token_share_delta_7d"] == round(0.30 - 0.20, 6)
    assert movers["anthropic/claude"]["token_share_delta_30d"] == round(0.30 - 0.10, 6)


def test_delta_is_null_when_no_snapshot_in_tolerance_window():
    today = _snapshot("2026-07-16", [_row(1, "anthropic/claude", 0.30)])
    facts = compute_facts([("2026-07-16", today)])

    movers = {m["model"]: m for m in facts["rankings"]["movers"]}
    assert movers["anthropic/claude"]["rank_delta_7d"] is None
    assert movers["anthropic/claude"]["rank_delta_30d"] is None


def test_tone_quiet_when_nothing_notable():
    today = _snapshot("2026-07-16", [_row(1, "anthropic/claude", 0.30)])
    yesterday = _snapshot("2026-07-15", [_row(1, "anthropic/claude", 0.301)])
    facts = compute_facts([("2026-07-15", yesterday), ("2026-07-16", today)])
    assert compute_tone(facts) == "quiet"


def test_tone_notable_on_new_entrant():
    yesterday = _snapshot("2026-07-15", [_row(1, "anthropic/claude", 0.30)])
    today = _snapshot("2026-07-16", [_row(1, "anthropic/claude", 0.30), _row(2, "google/gemini", 0.10)])
    facts = compute_facts([("2026-07-15", yesterday), ("2026-07-16", today)])
    assert compute_tone(facts) == "notable"


def test_tone_big_day_on_record():
    day1 = _snapshot("2026-07-15", [_row(1, "anthropic/claude", 0.20)])
    day2 = _snapshot("2026-07-16", [_row(1, "anthropic/claude", 0.35)])
    facts = compute_facts([("2026-07-15", day1), ("2026-07-16", day2)])
    assert compute_tone(facts) == "big_day"


def test_record_disqualified_by_backfilled_prior_day():
    """M2.5: history now spans a backfilled range (e.g. from OpenRouter's
    historical dataset API, long before this project's CI pipeline existed)
    plus recent CI-produced days. A model matching an old backfilled peak
    must NOT be flagged as an all-time record — compute_facts doesn't (and
    shouldn't) know or care which days came from backfill vs the live
    pipeline, it just needs to see the deep history."""
    backfilled_peak = _snapshot("2025-03-01", [_row(1, "anthropic/claude", 0.45)])
    recent_day = _snapshot("2026-07-15", [_row(1, "anthropic/claude", 0.40)])
    today = _snapshot("2026-07-16", [_row(1, "anthropic/claude", 0.40)])  # matches recent, not a new high
    facts = compute_facts([("2025-03-01", backfilled_peak), ("2026-07-15", recent_day), ("2026-07-16", today)])

    assert facts["rankings"]["records"] == []


def test_record_still_fires_when_it_exceeds_backfilled_history():
    backfilled_peak = _snapshot("2025-03-01", [_row(1, "anthropic/claude", 0.45)])
    recent_day = _snapshot("2026-07-15", [_row(1, "anthropic/claude", 0.40)])
    today = _snapshot("2026-07-16", [_row(1, "anthropic/claude", 0.50)])  # exceeds the backfilled peak too
    facts = compute_facts([("2025-03-01", backfilled_peak), ("2026-07-15", recent_day), ("2026-07-16", today)])

    records = facts["rankings"]["records"]
    assert any(r["type"] == "all_time_token_share" and r["model"] == "anthropic/claude" for r in records)


def test_tie_in_rankings_does_not_crash():
    yesterday = _snapshot("2026-07-15", [_row(1, "anthropic/claude", 0.20), _row(2, "openai/gpt", 0.20)])
    today = _snapshot("2026-07-16", [_row(1, "anthropic/claude", 0.20), _row(2, "openai/gpt", 0.20)])
    facts = compute_facts([("2026-07-15", yesterday), ("2026-07-16", today)])
    assert len(facts["rankings"]["movers"]) == 2
