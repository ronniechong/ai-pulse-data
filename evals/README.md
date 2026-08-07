# Eval suite

20 frozen `facts.json`-shaped fixtures covering quiet day, big mover, new
entrant, dropout, both record types, insufficient history, adversarial model
name, tie in rankings, unmapped provider, multi-fact day, three "poisoned"
LLM-output fixtures, and five "faithful paraphrase" regression fixtures
covering known false-positive shapes:
- a model narrated as `{ProviderDisplayName}/{suffix}` with trailing
  punctuation instead of the raw slug
- the same pattern for a provider whose display name contains a space, such
  as "Moonshot AI" (this broke the model-mention regex and the
  allowed-entities set)
- a percentage figure rounded to 2 decimal places instead of 0/1 (rejected as
  "unverified" purely on string-format mismatch)
- a model narrated without its trailing release-date suffix (e.g.
  `openai/gpt-5.6-sol-pro` for the real `openai/gpt-5.6-sol-pro-20260709`),
  and — preemptively, same root cause — a model narrated without its
  trailing `:free`-style variant tag
- a record-streak-continuation fixture: `streak_days > 1` on an
  `all_time_token_share` record must read as `notable`, not `big_day` —
  without this, a model on a long uptrend re-triggers `big_day` and the same
  headline shape every single day

Plus a fixture proving the date/tag-suffix stripping doesn't over-widen the
allow-set (a fabricated model that merely resembles a real one is still
rejected).

`_slug_variants()` in `commentary.py` generalizes this class of false
positive: rather than special-casing each incident, it strips the modifiers
(trailing release date, trailing `:tag`) an LLM commonly treats as incidental
to a model's "name," and adds every combination to the allow-set. New
incidents of this shape should extend `_slug_variants()` and add a fixture
here, not patch `validate_entities_and_numbers` directly.

**Mocked by default, not a live-LLM eval.** Each fixture runs through the
deterministic path only: `compute_tone`, `render_template_commentary`, and
`validate_entities_and_numbers` — no OpenRouter call, no API key needed. This
was a deliberate choice: a suite that hits the real model on every push
touching `prompts/`, `facts.py`, or `commentary.py` would need
`OPENROUTER_API_KEY` available to that CI path and would spend money on every
such push. The production daily run already exercises the real LLM once a
day; these fixtures instead guard the parts that don't require the model —
the facts engine's correctness and the entity/number validator's ability to
catch fabricated content (the two "poisoned" fixtures simulate a bad LLM
output and assert the validator rejects it).

Run standalone: `uv run python evals/run_evals.py`
Also runs automatically under `uv run pytest` via `tests/test_evals.py`
(parametrized, one fixture per test case) — this is what CI actually gates on.

To eval the real model manually against a fixture, load its `facts` field and
call `aipulse.commentary.generate_commentary(facts)` with
`COMMENTARY_ENABLED=true` and a real `OPENROUTER_API_KEY` set.
