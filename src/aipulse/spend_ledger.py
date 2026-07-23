"""Month-to-date spend tracking for the commentary LLM call. Refuses the call
before it happens if the ledger already shows the month over cap — the ledger
is the enforcement point, not a monitoring-only log."""

import json
from datetime import UTC, datetime

from aipulse.config import SPEND_CAP_USD_PER_MONTH, SPEND_LEDGER_PATH


def _current_month() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


def load_ledger() -> dict:
    if not SPEND_LEDGER_PATH.exists():
        return {"months": {}}
    return json.loads(SPEND_LEDGER_PATH.read_text())


def _write_ledger(ledger: dict) -> None:
    SPEND_LEDGER_PATH.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n")


def month_to_date_cost(ledger: dict, month: str | None = None) -> float:
    month = month or _current_month()
    return ledger.get("months", {}).get(month, {}).get("cost_usd", 0.0)


def within_budget(ledger: dict, month: str | None = None) -> bool:
    return month_to_date_cost(ledger, month) < SPEND_CAP_USD_PER_MONTH


def lifetime_totals(ledger: dict) -> dict:
    """Sums every month ever recorded. `calls` only ever counts successful,
    validated LLM generations (see commentary.py — a rejected/errored attempt
    never reaches record_call), so this is real spend against real usable
    output, not spend against every attempt."""
    months = ledger.get("months", {}).values()
    return {
        "cost_usd": round(sum(m.get("cost_usd", 0.0) for m in months), 6),
        "calls": sum(m.get("calls", 0) for m in months),
    }


def record_call(
    ledger: dict,
    *,
    cost_usd: float,
    input_tokens: int,
    output_tokens: int,
    month: str | None = None,
) -> dict:
    """Returns the updated ledger; caller is responsible for persisting it
    (call save_ledger) so a dry-run / test can inspect before writing."""
    month = month or _current_month()
    months = dict(ledger.get("months", {}))
    entry = dict(months.get(month, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}))
    entry["calls"] += 1
    entry["input_tokens"] += input_tokens
    entry["output_tokens"] += output_tokens
    entry["cost_usd"] = round(entry["cost_usd"] + cost_usd, 6)
    months[month] = entry
    return {"months": months}


def save_ledger(ledger: dict) -> None:
    _write_ledger(ledger)
