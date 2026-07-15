from aipulse import quality


def _rankings(shares, count=50):
    models = [
        {
            "model": f"m{i}",
            "total_tokens": 100 - i,
            "token_share": shares[i] if i < len(shares) else 0.01,
        }
        for i in range(count)
    ]
    return {"models": models}


def test_row_count_bounds_pass():
    normalized = _rankings([0.2], count=50)
    assert quality.check_row_count_bounds("rankings", normalized) == []


def test_row_count_bounds_fail_too_few():
    normalized = _rankings([0.2], count=5)
    violations = quality.check_row_count_bounds("rankings", normalized)
    assert len(violations) == 1
    assert "row count 5" in violations[0]


def test_row_count_vs_previous_flags_big_drop():
    current = _rankings([0.2], count=10)
    previous = _rankings([0.2], count=50)
    violations = quality.check_row_count_vs_previous("rankings", current, previous)
    assert len(violations) == 1


def test_row_count_vs_previous_ignores_small_drop():
    current = _rankings([0.2], count=48)
    previous = _rankings([0.2], count=50)
    assert quality.check_row_count_vs_previous("rankings", current, previous) == []


def test_row_count_vs_previous_no_previous_run_yet():
    current = _rankings([0.2], count=5)
    assert quality.check_row_count_vs_previous("rankings", current, None) == []


def test_check_nulls_catches_empty_model_name():
    normalized = {"models": [{"model": "", "total_tokens": 10}]}
    violations = quality.check_nulls("rankings", normalized)
    assert len(violations) == 1


def test_check_nulls_catches_negative_tokens():
    normalized = {"models": [{"model": "a", "total_tokens": -5}]}
    violations = quality.check_nulls("rankings", normalized)
    assert len(violations) == 1


def test_top1_token_share_within_band():
    normalized = _rankings([0.3], count=50)
    assert quality.check_top1_token_share(normalized) == []


def test_top1_token_share_too_dominant():
    normalized = _rankings([0.9], count=50)
    violations = quality.check_top1_token_share(normalized)
    assert len(violations) == 1


def test_top1_token_share_ignores_other_row():
    models = [{"model": "other", "total_tokens": 1000, "token_share": 0.9}]
    models += [{"model": f"m{i}", "total_tokens": 10, "token_share": 0.02} for i in range(10)]
    normalized = {"models": models}
    assert quality.check_top1_token_share(normalized) == []
