import json

import pytest

from aipulse import commentary, notify, publish, spend_ledger
from aipulse.pipeline import run_facts_and_commentary


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(publish, "DATA_DIR", data_dir)
    monkeypatch.setattr(publish, "LATEST_DIR", data_dir / "latest")
    monkeypatch.setattr(publish, "MANIFEST_PATH", data_dir / "manifest.json")
    monkeypatch.setattr(spend_ledger, "SPEND_LEDGER_PATH", tmp_path / "spend-ledger.json")
    monkeypatch.setattr(notify, "notify", lambda *a, **k: None)
    monkeypatch.setattr(commentary, "COMMENTARY_ENABLED", False)  # template fallback, no network
    return data_dir


def _write_rankings(data_dir, date_str: str, models: list[dict]) -> None:
    payload = {"generated_at": f"{date_str}T00:00:00+00:00", "date": date_str, "models": models}
    dated_dir = data_dir / date_str
    dated_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "latest").mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload)
    (dated_dir / "rankings.json").write_text(text)
    (data_dir / "latest" / "rankings.json").write_text(text)


def _row(rank, model, token_share):
    return {"rank": rank, "model": model, "total_tokens": int(token_share * 10**9), "token_share": token_share}


def test_skips_when_rankings_status_not_ok(_isolate):
    status = run_facts_and_commentary("2026-07-16", {"status": "degraded"})
    assert status["status"] == "skipped"


def test_skips_when_no_history_for_today(_isolate):
    # rankings status says "ok" but no file was actually written for today (edge case).
    status = run_facts_and_commentary("2026-07-16", {"status": "ok"})
    assert status["status"] == "skipped"


def test_publishes_facts_and_commentary_when_rankings_ok(_isolate):
    _write_rankings(_isolate, "2026-07-15", [_row(1, "anthropic/claude", 0.30)])
    _write_rankings(_isolate, "2026-07-16", [_row(1, "anthropic/claude", 0.30), _row(2, "google/gemini", 0.10)])

    status = run_facts_and_commentary("2026-07-16", {"status": "ok"})

    assert status["status"] == "ok"
    facts = json.loads((publish.LATEST_DIR / "facts.json").read_text())
    assert [e["model"] for e in facts["rankings"]["new_entrants"]] == ["google/gemini"]

    commentary_out = json.loads((publish.LATEST_DIR / "commentary.json").read_text())
    assert commentary_out["tone"] == "notable"
    assert (publish.DATA_DIR / "2026-07-16" / "facts.json").exists()
    assert (publish.DATA_DIR / "2026-07-16" / "commentary.json").exists()


def test_facts_step_failure_is_degraded_not_a_crash(_isolate, monkeypatch):
    _write_rankings(_isolate, "2026-07-16", [_row(1, "anthropic/claude", 0.30)])

    def _boom(history):
        raise RuntimeError("simulated facts engine bug")

    monkeypatch.setattr("aipulse.pipeline.compute_facts", _boom)
    status = run_facts_and_commentary("2026-07-16", {"status": "ok"})
    assert status["status"] == "degraded"
    assert not (publish.LATEST_DIR / "facts.json").exists()
