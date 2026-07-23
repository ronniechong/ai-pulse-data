import json
from datetime import date, timedelta

import pytest
import responses

from aipulse import ai_transparency, spend_ledger
from aipulse.config import LANGFUSE_HOST, LANGFUSE_TRACES_PATH
from aipulse.errors import SourceFetchError


def _trace(output, latency_ms=1000.0):
    return {"output": output, "metadata": {"latency_ms": latency_ms}}


def test_compute_llm_reliability_mixed_attempts():
    traces = [_trace({"headline": "x"}, 4000), _trace(None, 200), _trace(None, 150)]
    result = ai_transparency.compute_llm_reliability(traces)
    assert result == {
        "attempts_checked": 3,
        "success_count": 1,
        "fallback_count": 2,
        "success_rate": pytest.approx(0.3333, rel=1e-3),
        "avg_latency_ms": pytest.approx((4000 + 200 + 150) / 3, rel=1e-3),
    }


def test_compute_llm_reliability_empty():
    result = ai_transparency.compute_llm_reliability([])
    assert result["attempts_checked"] == 0
    assert result["success_rate"] is None
    assert result["avg_latency_ms"] is None


def test_compute_tone_distribution_reads_local_history(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_transparency, "DATA_DIR", tmp_path)
    today = date.today()
    for offset, tone in [(0, "quiet"), (1, "notable"), (2, "big_day"), (3, "notable")]:
        day_dir = tmp_path / (today - timedelta(days=offset)).isoformat()
        day_dir.mkdir(parents=True)
        (day_dir / "commentary.json").write_text(json.dumps({"tone": tone}))

    result = ai_transparency.compute_tone_distribution(window_days=30)
    assert result == {"quiet": 1, "notable": 2, "big_day": 1, "days_checked": 4}


def test_compute_tone_distribution_skips_missing_days(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_transparency, "DATA_DIR", tmp_path)
    result = ai_transparency.compute_tone_distribution(window_days=5)
    assert result == {"quiet": 0, "notable": 0, "big_day": 0, "days_checked": 0}


@responses.activate
def test_fetch_commentary_traces_paginates(monkeypatch):
    monkeypatch.setattr(ai_transparency, "LANGFUSE_PUBLIC_KEY", "test-public")
    monkeypatch.setattr(ai_transparency, "LANGFUSE_SECRET_KEY", "test-secret")
    responses.add(
        responses.GET,
        f"{LANGFUSE_HOST}{LANGFUSE_TRACES_PATH}",
        json={"data": [{"id": "a"}], "meta": {"page": 1, "totalPages": 2}},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{LANGFUSE_HOST}{LANGFUSE_TRACES_PATH}",
        json={"data": [{"id": "b"}], "meta": {"page": 2, "totalPages": 2}},
        status=200,
    )
    traces = ai_transparency.fetch_commentary_traces(date.today() - timedelta(days=30))
    assert [t["id"] for t in traces] == ["a", "b"]


@responses.activate
def test_fetch_commentary_traces_raises_source_fetch_error_on_http_failure(monkeypatch):
    monkeypatch.setattr(ai_transparency, "LANGFUSE_PUBLIC_KEY", "test-public")
    monkeypatch.setattr(ai_transparency, "LANGFUSE_SECRET_KEY", "test-secret")
    responses.add(
        responses.GET,
        f"{LANGFUSE_HOST}{LANGFUSE_TRACES_PATH}",
        json={"error": "unauthorized"},
        status=401,
    )
    with pytest.raises(SourceFetchError):
        ai_transparency.fetch_commentary_traces(date.today())


def test_fetch_commentary_traces_raises_when_credentials_missing(monkeypatch):
    monkeypatch.setattr(ai_transparency, "LANGFUSE_PUBLIC_KEY", "")
    with pytest.raises(SourceFetchError):
        ai_transparency.fetch_commentary_traces(date.today())


def test_compute_ai_transparency_bundles_all_signals(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_transparency, "DATA_DIR", tmp_path)
    monkeypatch.setattr(ai_transparency, "fetch_commentary_traces", lambda since: [_trace({"h": 1}, 500)])
    monkeypatch.setattr(spend_ledger, "SPEND_LEDGER_PATH", tmp_path / "spend-ledger.json")
    monkeypatch.setattr(ai_transparency, "run_all_fixtures", lambda: {"total": 17, "passed": 17, "failed": 0})

    result = ai_transparency.compute_ai_transparency("2026-07-23T00:00:00Z")
    assert result["llm_reliability"]["success_count"] == 1
    assert result["tone_distribution"]["days_checked"] == 0
    assert result["spend"]["month_to_date_usd"] == 0.0
    assert result["window_days"] == 30
    assert result["eval_suite"] == {"total": 17, "passed": 17, "failed": 0}


def test_compute_eval_suite_health_reports_real_current_fixtures(monkeypatch):
    monkeypatch.setattr(
        ai_transparency, "run_all_fixtures", lambda: {"total": 5, "passed": 4, "failed": 1, "failures": {"x": []}}
    )
    assert ai_transparency.compute_eval_suite_health() == {"total": 5, "passed": 4, "failed": 1}


def test_compute_spend_includes_lifetime_and_cost_per_generation():
    ledger = {
        "months": {
            "2026-06": {"calls": 2, "cost_usd": 0.02},
            "2026-07": {"calls": 3, "cost_usd": 0.03},
        }
    }
    result = ai_transparency.compute_spend(ledger)
    assert result["lifetime_usd"] == 0.05
    assert result["lifetime_calls"] == 5
    assert result["cost_per_generation_usd"] == pytest.approx(0.01)


def test_compute_spend_cost_per_generation_none_when_no_calls():
    result = ai_transparency.compute_spend({"months": {}})
    assert result["lifetime_calls"] == 0
    assert result["cost_per_generation_usd"] is None
