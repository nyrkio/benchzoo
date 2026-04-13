"""LLM-based fallback parser using a local Ollama model.

**Experimental / optional.** Mirror of :mod:`llm_anthropic` but calls
a local Ollama instance instead of the Anthropic API. Same contract,
same prompt, same tradeoffs — just offline and privacy-preserving.

## Prerequisites

1. Install Ollama: https://ollama.com
2. Pull a recommended model. For structured benchmark-output parsing
   these are the tested sweet spots::

       ollama pull qwen2.5-coder:3b     # ~2 GB, coder-tuned (default)
       ollama pull llama3.2:3b          # ~2 GB, general-purpose
       ollama pull phi3.5:latest        # ~2.3 GB, instruction-tuned

3. Have Ollama running (``ollama serve`` or the desktop app).

By default this parser talks to ``http://localhost:11434`` — override
via the ``host`` kwarg or the ``OLLAMA_HOST`` env var.

## Tradeoffs vs. ``llm_anthropic``

- **Pro**: no API cost, works offline, data never leaves the machine.
- **Pro**: deterministic with ``temperature=0`` + fixed seed.
- **Con**: lower accuracy on rich / nested formats (3B models are
  materially weaker than frontier models at structured extraction).
- **Con**: slower on CPU (3B Q4 ≈ 1-5 s per parse on a modern laptop).

## Example

    from benchzoo.parsers import llm_local
    results = llm_local.parse(some_weird_output)
    # or with a specific model:
    results = llm_local.parse(some_weird_output, model="llama3.2:3b")
"""

from __future__ import annotations

import json
import os
from urllib import error as _urlerror
from urllib import request as _urlrequest

from benchzoo.parsers._llm_prompt import SYSTEM_PROMPT, build_user_prompt


DEFAULT_MODEL = "qwen2.5-coder:3b"
DEFAULT_HOST = "http://localhost:11434"
DEFAULT_TIMEOUT_S = 120.0


def parse(
    content: bytes | str,
    *,
    format_hint: str | None = None,
    model: str = DEFAULT_MODEL,
    host: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> list[dict]:
    """Parse ``content`` into Nyrkiö JSON via a local Ollama instance.

    Uses Ollama's ``/api/chat`` endpoint with ``format: "json"`` to
    enforce valid-JSON decoding at the model level — the biggest
    accuracy boost available for small local models.

    Raises ``RuntimeError`` on decode failure or unreachable host.
    """
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    base = host or os.environ.get("OLLAMA_HOST") or DEFAULT_HOST
    base = base.rstrip("/")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_user_prompt(content, format_hint=format_hint),
            },
        ],
        # Ollama accepts "json" here; together with our "return ONLY a
        # JSON array" instruction this constrains decoding sufficiently
        # that small (~3 B parameter) models produce valid JSON.
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.0,
            "seed": 0,
        },
    }

    req = _urlrequest.Request(
        f"{base}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    try:
        with _urlrequest.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except _urlerror.URLError as exc:
        raise RuntimeError(
            f"Could not reach Ollama at {base}: {exc}. "
            f"Is `ollama serve` running and is the model `{model}` pulled?"
        ) from exc

    envelope = json.loads(body)
    message = envelope.get("message", {})
    text = (message.get("content") or "").strip()

    # Ollama's format=json mode always returns a JSON *value* in
    # `message.content`. The model may still wrap the array in an
    # object like {"results": [...]} — accept both.
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Ollama returned non-JSON content: {text[:200]}..."
        ) from exc

    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        # Small models commonly wrap the array in a single-key object.
        for key in ("results", "tests", "data", "array", "items"):
            inner = value.get(key)
            if isinstance(inner, list):
                return inner

    raise RuntimeError(
        f"Ollama returned unexpected shape (expected JSON array, "
        f"got {type(value).__name__}): {text[:200]}..."
    )
