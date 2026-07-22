# Runbook

Operational procedures for `ai-pulse-data`. For *why* each control exists,
see the Decision Log in `work-docs` (not this repo). For what each
data-quality gate checks, see `DATA_QUALITY.md`.

## Kill switches

Two independent levels, narrowest first.

**1. Disable AI commentary only** (keeps rankings/facts/apps/etc. publishing
normally, commentary falls back to a deterministic template):
- GitHub → this repo → Settings → Secrets and variables → Actions →
  Variables → set `COMMENTARY_ENABLED` to `false` (or delete it — unset
  defaults to disabled).
- Takes effect on the next pipeline run, no code change, no redeploy.
- Verified fallback path: `generate_commentary()` in `commentary.py` checks
  this flag first and returns `render_template_commentary(facts)`
  immediately if disabled — the LLM is never called.

**2. Stop the whole daily pipeline** (nothing publishes, site keeps serving
last-known-good data indefinitely):
- GitHub → this repo → Actions → "daily-pipeline" workflow → "..." menu →
  Disable workflow. Or `gh workflow disable daily-pipeline.yml` if `gh` is
  authenticated.
- Re-enable the same way when ready. No data is lost either way — the last
  successful commit stays live on `raw.githubusercontent.com`/jsDelivr.

## Bad-commentary response

Two different failure shapes, two different responses:

**Caught by validation (expected path, no action needed):** every model
name and percentage in the LLM's output must trace back to `facts.json`
(`validate_entities_and_numbers` in `commentary.py`). A fabricated model or
made-up figure fails validation, triggers one retry
(`COMMENTARY_MAX_RETRIES = 1`), and falls back to the template on a second
failure. An ntfy alert ("AI Pulse: commentary fell back to template")
fires either way — this is the system working as designed, not an incident.
Check the alert's error text and the corresponding Langfuse trace (the
`prompt_version` tag on it, currently `commentary-v2`) if you want to
understand *why* it failed, but nothing is broken and nothing needs fixing
before the next run.

**Passed validation but is still wrong** (real incident — wrong tone, badly
phrased, technically-true-but-misleading): validation only checks that
entities/numbers are real, not that the writing is good.
1. Flip kill switch #1 above immediately — stops any more bad commentary
   from publishing while you investigate.
2. The bad `commentary.json` is already committed and live. Revert it:
   `git revert <bad-commit-sha> -- data/latest/commentary.json
   data/<date>/commentary.json` (or hand-edit and commit a correction —
   either way, push directly, this is a manual override of automated
   content).
3. Read the current prompt (`prompts/{COMMENTARY_PROMPT_VERSION}.md`, e.g.
   `prompts/commentary-v2.md`) and the Langfuse trace for that day to decide
   whether it's a prompt problem (tune the prompt, bump to the next
   `commentary-vN`, update `COMMENTARY_PROMPT_VERSION` in `config.py`) or a
   one-off model quirk (leave the prompt alone, re-enable, watch the next
   run).
4. Re-enable only once you're confident the fix addresses the actual cause.

## Key rotation

All secrets live in GitHub → this repo → Settings → Secrets and variables →
Actions. Rotating any of them requires no code change — the workflow reads
them fresh from `secrets.*`/`vars.*` on every run.

| Secret | Where to get a new one | Notes |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter.ai → Keys | Spend-capped at $5 prepaid, auto-reload off, at the account level (not just the in-app $2/mo ledger check) — confirm the new key inherits the same cap before rotating in |
| `HF_TOKEN` | huggingface.co → Settings → Access Tokens | Read-only scope is sufficient — never issue a write-scoped token here |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | cloud.langfuse.com → project settings | Rotate both together — they're a pair |
| `NTFY_TOPIC` | Pick a new unpredictable topic name (ntfy topics are public-by-obscurity, anyone who knows the name can read it) | Update the phone subscription to the new topic *before* rotating, or you'll miss alerts during the gap |

Rotation steps: (1) generate the new credential upstream, (2) update the
GitHub secret, (3) trigger a manual `workflow_dispatch` run to confirm the
new credential actually works, (4) revoke the old credential upstream only
after step 3 succeeds.

## Purge procedure

**A secret was committed to git history** (not just pasted in chat — an
actual file in a commit): rotating the secret (above) is necessary but not
sufficient, since the old value stays readable in git history on a public
repo forever until rewritten.
1. Rotate the credential immediately (above) — this limits the blast radius
   regardless of what happens to history.
2. Rewrite history with `git filter-repo` (not `git rm` — that only removes
   it from new commits, old commits still have it) to strip the secret from
   every commit that ever contained it.
3. Force-push the rewritten history, then tell anyone with a local clone to
   re-clone rather than pull (their local history now diverges permanently).
4. This is the same method already flagged as needed if `sdk-geo-history.json`
   is ever removed for size reasons — see Deferred decisions in `work-docs`
   — filter-repo is the general tool for any "remove this from history for
   good" situation in this repo, not secret-specific.

**Bad data published to `data/latest/`** (corrupted file, wrong values, not
a secrets issue): revert forward, don't force-push.
`git revert <bad-commit-sha>` restores the previous `data/latest/*.json`
content as a new commit — the dashboard picks it up on its next manifest
poll, no coordination needed with anyone else's clone.

## Upstream-drift playbook

`DATA_QUALITY.md`'s gates (schema validation, row-count bounds, row-count-
vs-previous, null checks, top-1 share plausibility) catch this
automatically: the affected source's manifest entry flips to
`"status": "degraded"`, its `data/latest/` file is left untouched (last-good
data keeps serving), an ntfy alert fires, and every other source keeps
publishing normally (`pipeline.py`'s per-source isolation).

When an ntfy "degraded" alert fires:
1. Read the alert's error message first — schema-validation failures
   usually name the exact field that broke.
2. Reproduce locally: `uv run python -c "from aipulse.fetchers import
   <module>; print(<module>.<fetch_fn>())"` against the live API to see the
   raw response shape.
3. Decide fix vs wait: a genuine upstream schema change needs a code fix
   (update the pydantic model in `schemas.py`, and the transform in
   `transform.py` if field names moved) before the source recovers. A
   transient outage needs nothing — the next scheduled run will likely
   clear the degraded status on its own once the upstream API recovers.
4. No urgency pressure: the site is never showing broken data during this —
   it's showing yesterday's good data for that one source while everything
   else stays current. Fix at a normal pace, verify against the live API
   before pushing (this project's established pattern — see `work-docs`
   History log for examples), then confirm via a manual `workflow_dispatch`
   run that the source recovers to `"status": "ok"`.
