"""Facts-only LLM narration, with a deterministic template fallback that is
always schema-valid on its own. See prompts/commentary-v1.md for the prompt
and work-docs M2 design spec for the validation rationale.
"""

import json
import re
import sys
from datetime import UTC, datetime

import requests
from pydantic import ValidationError

from aipulse import notify, spend_ledger, tracing
from aipulse.config import (
    COMMENTARY_ENABLED,
    COMMENTARY_MAX_RETRIES,
    COMMENTARY_MODEL,
    COMMENTARY_PROMPT_VERSION,
    OPENROUTER_API_KEY,
    OPENROUTER_CHAT_URL,
    REPO_ROOT,
    SPEND_CAP_USD_PER_MONTH,
)
from aipulse.errors import CommentaryError
from aipulse.facts import compute_tone
from aipulse.schemas import CommentaryOutput

_TIMEOUT = 30
_PROMPT_PATH = REPO_ROOT / "prompts" / f"{COMMENTARY_PROMPT_VERSION}.md"

_MODEL_MENTION_RE = re.compile(r"[A-Za-z0-9][\w.\-]*/[\w.\-:]+")
_PERCENT_MENTION_RE = re.compile(r"(\d+(?:\.\d+)?)\s?%")


def _fmt_pct(value: float) -> set[str]:
    return {f"{value * 100:.1f}", f"{value * 100:.0f}"}


def _load_system_prompt() -> str:
    text = _PROMPT_PATH.read_text()
    start = text.index("## System instructions") + len("## System instructions")
    end = text.index("## User message template")
    return text[start:end].strip()


def _render_user_message(facts: dict, tone: str) -> str:
    return f"facts:\n{json.dumps(facts, indent=2)}\n\ntone (must match exactly): {tone}"


def _collect_allowed_entities(facts: dict) -> tuple[set[str], set[str]]:
    """Every model/provider name and every plausible percentage string that a
    faithful commentary could reference, derived only from `facts`."""
    rankings = facts["rankings"]
    models: set[str] = set()
    percents: set[str] = set()

    def _add_share(value: float | None) -> None:
        if value is not None:
            percents.update(_fmt_pct(value))
            percents.update(_fmt_pct(abs(value)))

    for m in rankings["movers"]:
        models.add(m["model"])
        for key in ("token_share_today", "token_share_delta_1d", "token_share_delta_7d", "token_share_delta_30d"):
            _add_share(m.get(key))
    for e in rankings["new_entrants"]:
        models.add(e["model"])
        _add_share(e["token_share"])
    for d in rankings["dropouts"]:
        models.add(d["model"])
        _add_share(d["last_token_share"])
    for r in rankings["records"]:
        models.add(r["model"])
        _add_share(r["value"])
    for p in rankings["provider_share"]:
        for key in ("token_share_today", "delta_1d", "delta_7d", "delta_30d"):
            _add_share(p.get(key))

    return models, percents


def validate_entities_and_numbers(parsed: dict, facts: dict) -> list[str]:
    """Every model slug and percentage figure mentioned in the commentary text
    must trace back to `facts`. Approximate for free text (formatting/rounding
    variance), but catches fabricated models and made-up figures."""
    allowed_models, allowed_percents = _collect_allowed_entities(facts)
    text = " ".join([parsed["headline"], parsed["summary"], *parsed["highlights"]])

    violations = []
    for match in _MODEL_MENTION_RE.findall(text):
        if match not in allowed_models:
            violations.append(f"unknown model referenced: {match!r}")
    for match in _PERCENT_MENTION_RE.findall(text):
        if match not in allowed_percents:
            violations.append(f"unverified percentage referenced: {match}%")
    return violations


def render_template_commentary(facts: dict) -> dict:
    """Always produces schema-valid, facts-only commentary with no LLM call."""
    rankings = facts["rankings"]
    tone = compute_tone(facts)
    highlights: list[str] = []

    for r in rankings["records"]:
        kind = "highest-ever token share" if r["type"] == "all_time_token_share" else "reached #1 for the first time"
        pct = next(iter(_fmt_pct(r["value"])))
        highlights.append(f"{r['model']} ({r['provider']}) hit a {kind} at {pct}%")

    for e in sorted(rankings["new_entrants"], key=lambda x: x["rank"])[:5]:
        highlights.append(f"{e['model']} ({e['provider']}) entered the top rankings at rank {e['rank']}")

    for d in sorted(rankings["dropouts"], key=lambda x: x["last_rank"])[:5]:
        highlights.append(f"{d['model']} ({d['provider']}) dropped out of the top rankings (last rank {d['last_rank']})")

    big_movers = sorted(
        (m for m in rankings["movers"] if m["rank_delta_1d"] is not None and abs(m["rank_delta_1d"]) >= 5),
        key=lambda m: -abs(m["rank_delta_1d"]),
    )
    for m in big_movers[:5]:
        direction = "up" if m["rank_delta_1d"] > 0 else "down"
        highlights.append(f"{m['model']} moved {direction} {abs(m['rank_delta_1d'])} ranks to #{m['rank_today']}")

    if not highlights:
        headline = "A quiet day in the rankings"
        summary = "No new entrants, dropouts, records, or significant movers today."
    else:
        headline = highlights[0][:100]
        summary = f"{len(highlights)} notable change(s) in today's rankings."

    return {"headline": headline, "summary": summary, "highlights": highlights, "tone": tone}


def _call_openrouter_chat(system_prompt: str, user_message: str) -> tuple[dict, dict]:
    if not OPENROUTER_API_KEY:
        raise CommentaryError("OPENROUTER_API_KEY is not set")

    body = {
        "model": COMMENTARY_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "response_format": {"type": "json_object"},
        "usage": {"include": True},
        "temperature": 0.3,
    }
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
    try:
        resp = requests.post(OPENROUTER_CHAT_URL, json=body, headers=headers, timeout=_TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, ValueError) as e:
        raise CommentaryError(f"OpenRouter chat completion failed: {e}") from e

    try:
        content = payload["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
        raise CommentaryError(f"OpenRouter chat completion returned unparseable content: {e}") from e

    return parsed, payload.get("usage", {})


def generate_commentary(facts: dict) -> dict:
    tone = compute_tone(facts)

    if not COMMENTARY_ENABLED:
        return render_template_commentary(facts)

    ledger = spend_ledger.load_ledger()
    if not spend_ledger.within_budget(ledger):
        notify.notify(
            title="AI Pulse: commentary skipped (spend cap)",
            message=f"Month-to-date spend at/over ${SPEND_CAP_USD_PER_MONTH:.2f} cap; using template commentary.",
            priority="high",
            tags="warning",
        )
        return render_template_commentary(facts)

    system_prompt = _load_system_prompt()
    user_message = _render_user_message(facts, tone)

    last_error: Exception | None = None
    for _attempt in range(COMMENTARY_MAX_RETRIES + 1):
        started_at = datetime.now(UTC)
        try:
            raw, usage = _call_openrouter_chat(system_prompt, user_message)
            parsed_dict = CommentaryOutput.model_validate(raw).model_dump()
            parsed_dict["tone"] = tone  # deterministic, never trusted from the LLM

            violations = validate_entities_and_numbers(parsed_dict, facts)
            if violations:
                raise CommentaryError("entity/number validation failed: " + "; ".join(violations))
        except (CommentaryError, ValidationError) as e:
            last_error = e
            ended_at = datetime.now(UTC)
            tracing.trace_commentary_call(
                prompt_version=COMMENTARY_PROMPT_VERSION,
                input_facts=facts,
                output=None,
                model=COMMENTARY_MODEL,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                latency_ms=(ended_at - started_at).total_seconds() * 1000,
                started_at=started_at,
                ended_at=ended_at,
                error=str(e),
            )
            continue
        else:
            ended_at = datetime.now(UTC)
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            cost_usd = usage.get("cost") or 0.0
            ledger = spend_ledger.record_call(
                ledger, cost_usd=cost_usd, input_tokens=input_tokens, output_tokens=output_tokens
            )
            spend_ledger.save_ledger(ledger)
            tracing.trace_commentary_call(
                prompt_version=COMMENTARY_PROMPT_VERSION,
                input_facts=facts,
                output=parsed_dict,
                model=COMMENTARY_MODEL,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                latency_ms=(ended_at - started_at).total_seconds() * 1000,
                started_at=started_at,
                ended_at=ended_at,
            )
            return parsed_dict

    print(f"[commentary] all attempts failed, using template fallback: {last_error}", file=sys.stderr)
    notify.notify(
        title="AI Pulse: commentary fell back to template",
        message=str(last_error),
        priority="default",
        tags="warning",
    )
    return render_template_commentary(facts)
