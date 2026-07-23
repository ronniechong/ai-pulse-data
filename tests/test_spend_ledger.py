from aipulse import spend_ledger


def test_lifetime_totals_sums_across_months():
    ledger = {
        "months": {
            "2026-07": {"calls": 5, "cost_usd": 0.05},
            "2026-08": {"calls": 3, "cost_usd": 0.021806},
        }
    }
    assert spend_ledger.lifetime_totals(ledger) == {"cost_usd": 0.071806, "calls": 8}


def test_lifetime_totals_empty_ledger():
    assert spend_ledger.lifetime_totals({"months": {}}) == {"cost_usd": 0.0, "calls": 0}
