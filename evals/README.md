# Eval suite

16 frozen `facts.json`-shaped fixtures covering the scenarios in the M2 design
spec (quiet day, big mover, new entrant, dropout, both record types,
insufficient history, adversarial model name, tie in rankings, unmapped
provider, multi-fact day, two "poisoned" LLM-output fixtures, and three
"faithful paraphrase" regression fixtures for real production false positives:
a model narrated as `{ProviderDisplayName}/{suffix}` with trailing punctuation
instead of the raw slug (2026-07-18), the same pattern for a provider whose
display name contains a space such as "Moonshot AI" (2026-07-19, previously
broke the model-mention regex and the allowed-entities set), and a percentage
figure rounded to 2 decimal places instead of 0/1 (2026-07-19, previously
rejected as "unverified" purely on string-format mismatch).

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
