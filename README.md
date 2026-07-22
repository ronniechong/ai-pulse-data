# ai-pulse-data

Fetchers, transforms, workflow, prompts, evals, and committed JSON snapshots
for [AI Pulse](https://github.com/ronniechong/ai-pulse-web) — a dashboard
tracking which AI models the world actually uses (rankings, provider share,
open vs closed source, geographic adoption), with an AI-generated daily
commentary layer.

Runs on a daily GitHub Actions cron: fetch → validate → normalize → diff →
commentary → commit. Data is served straight off this repo via
`raw.githubusercontent.com` / jsDelivr — no separate hosting.

Planning, architecture, and decision log are tracked outside this repo.

## Governance

The commentary layer (the one part of this pipeline that calls an LLM) is
built around six controls:

1. **Spend controls & kill switch** — a $5 prepaid OpenRouter credit with
   auto-reload off (exceeding it is structurally impossible, not just
   monitored), plus an in-app monthly ledger (`spend_ledger.py`) that
   refuses further LLM calls once month-to-date spend hits $2 and falls
   back to template commentary automatically. `COMMENTARY_ENABLED` is the
   manual equivalent — flip it off in the repo's Actions variables to force
   every run onto the template path, no code change, no redeploy.
2. **Tracing** — every commentary call is traced to Langfuse (prompt
   version, input facts, output, tokens, cost, latency), so any output can
   be audited back to exactly what it was given and what it cost.
3. **Prompt versioning** — the active prompt lives at `prompts/commentary-v2.md`
   (older versions kept for history), versioned by filename, PR-reviewed like
   code, and the version string is recorded on every trace.
4. **Eval gate** — CI runs a 14-fixture eval suite against any change to
   `prompts/`, the facts engine, or the output schema before it can merge
   (quiet day, big mover, new entrant, adversarial/poisoned inputs, etc.).
5. **Hallucination controls** — every model name and percentage the LLM
   writes must trace back to that day's computed facts
   (`validate_entities_and_numbers`); a fabricated figure triggers one retry
   then a deterministic, facts-only template fallback that never calls the
   LLM at all.
6. **Transparency** — the dashboard's `/about` page discloses the AI
   commentary, its facts-only constraint, the fallback behavior, and every
   upstream data source's license; `METRICS.md` documents every metric's
   definition and known caveats.

Loosely, this maps to NIST's AI Risk Management Framework's four functions:
**Govern** (prompt versioning, PR review, the spend cap as a hard boundary),
**Map** (transparency docs — disclosing what the system is and isn't),
**Measure** (tracing, the eval gate, entity/number validation as an
automated accuracy check), and **Manage** (the kill switch and template
fallback as the actual response when something goes wrong). This is a
portfolio-scale illustration of the mapping, not a claim of formal NIST AI
RMF conformance.

See `RUNBOOK.md` for the operational procedures behind each of these
(kill switch steps, key rotation, bad-commentary response, upstream-drift
playbook).
