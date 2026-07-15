"""Best-effort Langfuse tracing via the public ingestion REST API directly
(not the langfuse SDK) — keeps this repo's dependency footprint to
pydantic/dotenv/requests and avoids coupling to a fast-moving SDK's API.
Fails open exactly like notify.py: a broken/unreachable Langfuse must never
fail a pipeline run.
"""

import uuid
from datetime import UTC, datetime

import requests

from aipulse.config import LANGFUSE_HOST, LANGFUSE_INGESTION_PATH, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY

_TIMEOUT = 10


def trace_commentary_call(
    *,
    prompt_version: str,
    input_facts: dict,
    output: dict | None,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    latency_ms: float,
    started_at: datetime,
    ended_at: datetime,
    error: str | None = None,
) -> None:
    if not (LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY):
        return

    trace_id = str(uuid.uuid4())
    generation_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()

    batch = [
        {
            "id": str(uuid.uuid4()),
            "type": "trace-create",
            "timestamp": now,
            "body": {
                "id": trace_id,
                "name": "ai-pulse-commentary",
                "input": input_facts,
                "output": output,
                "metadata": {"prompt_version": prompt_version, "latency_ms": latency_ms},
                "tags": ["ai-pulse", prompt_version],
            },
        },
        {
            "id": str(uuid.uuid4()),
            "type": "generation-create",
            "timestamp": now,
            "body": {
                "id": generation_id,
                "traceId": trace_id,
                "name": "commentary-generation",
                "model": model,
                "input": input_facts,
                "output": output,
                "startTime": started_at.isoformat(),
                "endTime": ended_at.isoformat(),
                "usage": {
                    "input": input_tokens,
                    "output": output_tokens,
                    "total": input_tokens + output_tokens,
                    "unit": "TOKENS",
                },
                "usageDetails": {"input": input_tokens, "output": output_tokens},
                "costDetails": {"total": cost_usd},
                "level": "ERROR" if error else "DEFAULT",
                "statusMessage": error,
            },
        },
    ]

    try:
        requests.post(
            f"{LANGFUSE_HOST}{LANGFUSE_INGESTION_PATH}",
            json={"batch": batch},
            auth=(LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY),
            timeout=_TIMEOUT,
        )
    except requests.RequestException:
        pass
