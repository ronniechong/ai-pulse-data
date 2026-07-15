import json

import pytest

from aipulse import commentary, history_rollup, notify, publish, spend_ledger
from aipulse.errors import SourceFetchError
from aipulse.pipeline import run_facts_and_commentary, run_rankings_history_rollup


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(publish, "DATA_DIR", data_dir)
    monkeypatch.setattr(publish, "LATEST_DIR", data_dir / "latest")
    monkeypatch.setattr(publish, "MANIFEST_PATH", data_dir / "manifest.json")
    monkeypatch.setattr(history_rollup, "LATEST_DIR", data_dir / "latest")
    monkeypatch.setattr(spend_ledger, "SPEND_LEDGER_PATH", tmp_path / "spend-ledger.json")
    monkeypatch.setattr(notify, "notify", lambda *a, **k: None)
    monkeypatch.setattr(commentary, "COMMENTARY_ENABLED", False)  # template fallback, no network
    return data_dir


_OK = {"status": "ok"}


def _seed_rollup(date_str: str, models: list[dict]) -> None:
    """models: list of {"model": ..., "rank": ..., "token_share": ...}"""
    existing = history_rollup.load_rollup("rankings")["rows"]
    for m in models:
        existing.append({"date": date_str, "source": "pipeline", **m})
    history_rollup.save_rollup("rankings", existing)


def _row(rank, model, token_share):
    return {"rank": rank, "model": model, "token_share": token_share}


# --- run_facts_and_commentary -------------------------------------------


def test_skips_when_rankings_status_not_ok(_isolate):
    status = run_facts_and_commentary("2026-07-16", {"status": "degraded"}, _OK)
    assert status["status"] == "skipped"


def test_skips_when_rollup_status_not_ok(_isolate):
    status = run_facts_and_commentary("2026-07-16", _OK, {"status": "degraded"})
    assert status["status"] == "skipped"


def test_skips_when_no_history_for_today(_isolate):
    # both statuses say "ok" but the rollup has no row for today (edge case).
    status = run_facts_and_commentary("2026-07-16", _OK, _OK)
    assert status["status"] == "skipped"


def test_publishes_facts_and_commentary_when_rollup_has_today(_isolate):
    _seed_rollup("2026-07-15", [_row(1, "anthropic/claude", 0.30)])
    _seed_rollup("2026-07-16", [_row(1, "anthropic/claude", 0.30), _row(2, "google/gemini", 0.10)])

    status = run_facts_and_commentary("2026-07-16", _OK, _OK)

    assert status["status"] == "ok"
    facts = json.loads((publish.LATEST_DIR / "facts.json").read_text())
    assert [e["model"] for e in facts["rankings"]["new_entrants"]] == ["google/gemini"]

    commentary_out = json.loads((publish.LATEST_DIR / "commentary.json").read_text())
    assert commentary_out["tone"] == "notable"
    assert (publish.DATA_DIR / "2026-07-16" / "facts.json").exists()
    assert (publish.DATA_DIR / "2026-07-16" / "commentary.json").exists()


def test_facts_step_failure_is_degraded_not_a_crash(_isolate, monkeypatch):
    _seed_rollup("2026-07-16", [_row(1, "anthropic/claude", 0.30)])

    def _boom(history):
        raise RuntimeError("simulated facts engine bug")

    monkeypatch.setattr("aipulse.pipeline.compute_facts", _boom)
    status = run_facts_and_commentary("2026-07-16", _OK, _OK)
    assert status["status"] == "degraded"
    assert not (publish.LATEST_DIR / "facts.json").exists()


# --- run_rankings_history_rollup -----------------------------------------


def test_rollup_step_merges_fresh_window_and_publishes_ok(_isolate, monkeypatch):
    from aipulse.schemas import OpenRouterRankingRow

    window_rows = [
        OpenRouterRankingRow(date="2026-07-15", model_permaslug="anthropic/claude", total_tokens=100),
        OpenRouterRankingRow(date="2026-07-16", model_permaslug="anthropic/claude", total_tokens=100),
    ]
    monkeypatch.setattr("aipulse.pipeline.openrouter.fetch_rankings_window", lambda: window_rows)

    status = run_rankings_history_rollup("2026-07-16")

    assert status["status"] == "ok"
    rollup = history_rollup.load_rollup("rankings")
    dates = {r["date"] for r in rollup["rows"]}
    assert dates == {"2026-07-15", "2026-07-16"}
    assert all(r["source"] == "pipeline" for r in rollup["rows"])


def test_rollup_step_degrades_gracefully_on_fetch_failure(_isolate, monkeypatch):
    def _boom():
        raise SourceFetchError("simulated: rankings-daily window fetch failed")

    monkeypatch.setattr("aipulse.pipeline.openrouter.fetch_rankings_window", _boom)

    status = run_rankings_history_rollup("2026-07-16")

    assert status["status"] == "degraded"
    assert history_rollup.load_rollup("rankings")["rows"] == []


def test_rollup_step_preserves_prior_history_on_later_failure(_isolate, monkeypatch):
    _seed_rollup("2026-07-15", [_row(1, "anthropic/claude", 0.30)])

    def _boom():
        raise SourceFetchError("simulated outage")

    monkeypatch.setattr("aipulse.pipeline.openrouter.fetch_rankings_window", _boom)
    status = run_rankings_history_rollup("2026-07-16")

    assert status["status"] == "degraded"
    rollup = history_rollup.load_rollup("rankings")
    assert [r["date"] for r in rollup["rows"]] == ["2026-07-15"]
