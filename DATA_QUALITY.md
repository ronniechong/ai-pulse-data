# Data quality

Every gate below runs per source, per pipeline run. **Any failure — schema or
quality — triggers the same response**: the source is skipped, its
`data/latest/<file>.json` is left exactly as the last successful run wrote it
(git history is the "last good" store, nothing is copied forward), its
`manifest.json` entry flips to `"status": "degraded"` with `last_success`
still pointing at the last date it published, and an ntfy alert fires. Other
sources are unaffected — see `src/aipulse/pipeline.py::run_source`.

There is no silent partial-publish path: a source either passes every gate
below and gets a fresh dated snapshot, or nothing about it changes this run.

## Gates

### 1. Schema validation
Every raw row from every source is parsed through a pydantic model
(`src/aipulse/schemas.py`) before anything else happens. Unexpected types,
missing required fields, or an empty/malformed response fail this
immediately. Catches: upstream API breaking changes, outages that return an
HTML error page instead of JSON, auth failures.

### 2. Row-count bounds
Each source has a plausible absolute row-count range
(`config.QUALITY_ROW_BOUNDS`), e.g. rankings should have ~50 rows (top-50 +
`other`), HF trending exactly the requested limit. Catches: an API silently
truncating or paginating differently than expected, a query returning an
empty-but-valid response.

### 3. Row-count vs previous run
A source's row count must not drop more than 50% versus its own last
published run (`quality.check_row_count_vs_previous`). Catches: partial
upstream outages that still return HTTP 200 with a valid-but-incomplete
payload — the kind of failure schema validation alone can't see.

### 4. Null / sanity checks
Per-row spot checks that required string fields aren't empty and numeric
fields (tokens, downloads) aren't negative (`quality.check_nulls`). Catches:
malformed individual rows that pass schema typing but are semantically
garbage (e.g. an empty model name).

### 5. Top-1 token-share plausibility band
Only applies to `rankings`. The leading model's share of total top-50 token
volume (excluding the `other` row) must fall within
`[TOP1_TOKEN_SHARE_MIN, TOP1_TOKEN_SHARE_MAX]` = `[2%, 60%]`
(`quality.check_top1_token_share`). Catches: aggregation bugs where one row
absorbs (or loses) most of the volume — a real data event would still show
significant token spread across the top 50.

## Attribution requirements

- **OpenRouter** (`rankings.json`, `apps.json`): must be cited as
  `Source: OpenRouter (openrouter.ai/rankings), as of {as_of}` wherever this
  data is displayed or republished (enforced in the dashboard's `/about`
  page at M3).
- **Anthropic Economic Index** (`geo-adoption.json`): CC-BY licensed, sourced
  from `huggingface.co/datasets/Anthropic/EconomicIndex`. Attribution string
  stored on the payload itself (`source` field).
- **Hugging Face Hub** (`hf-trending.json`) and **ClickPy/PyPI**
  (`sdk-geo.json`): no formal citation requirement found, but both are noted
  with a `source` field on their payloads for transparency.

## Known metric caveats (carried forward to M3's METRICS.md)

- Token counts are each provider's own tokenizer — not directly comparable
  across rows within `rankings.json`.
- OpenRouter is one (large) routing platform, not the whole market —
  selection bias toward API-first developers.
- HF `downloads` is a rolling window count, not inference usage; open-weight
  pulls only.
- PyPI SDK install counts (`sdk-geo.json`) can be inflated by CI/CD
  reinstalls — not a clean proxy for active usage.
- `geo-adoption.json` uses ISO 3166-1 **alpha-3** country codes (e.g. `USA`);
  `sdk-geo.json` uses ISO 3166-1 **alpha-2** (e.g. `US`) because that's what
  each upstream source returns natively. Any cross-referencing between the
  two at dashboard time needs a code-set conversion.
