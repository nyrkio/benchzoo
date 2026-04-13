"""LLM-based fallback parser using the Anthropic API.

**Experimental / optional.** This parser is a catch-all for benchmark
formats that benchzoo does not have a dedicated parser for. It calls
the Anthropic Messages API with the raw content, a concise Nyrkiö
schema description, and a handful of few-shot examples pulled from
the benchzoo fixture corpus; the model returns a JSON array matching
the parser contract.

**Tradeoffs** vs. format-specific parsers:
- Non-deterministic: two invocations on the same input may differ.
- Costs money (API calls). Prompt caching mitigates most of it.
- Network-dependent.
- May hallucinate plausible-looking values from ambiguous input.

**When to reach for this:**
- You have a proprietary / one-off format that benchzoo does not
  support and never will (one-shot analysis, not a long-term pipeline).
- You are **bootstrapping** a new format parser: let the LLM parse,
  read its output, and use that as the starting point for writing
  the deterministic parser.
- Triage: "is this format supported?" / "which parser should I use?"

**Not appropriate for** production change-detection pipelines, CI
gates, or anything whose correctness you actually care about.

## Environment

Reads ``ANTHROPIC_API_KEY`` from the environment (or the ``api_key``
kwarg). The ``anthropic`` package must be installed::

    pip install anthropic

## Example

    from benchzoo.parsers import llm_anthropic
    results = llm_anthropic.parse(some_weird_output)
"""

from __future__ import annotations

import json
import os

from benchzoo.parsers._llm_prompt import SYSTEM_PROMPT, build_user_prompt


DEFAULT_MODEL = "claude-sonnet-4-5"
DEFAULT_MAX_TOKENS = 4096


def parse(
    content: bytes | str,
    *,
    format_hint: str | None = None,
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> list[dict]:
    """Parse ``content`` into Nyrkiö JSON via the Anthropic API.

    ``format_hint`` is passed to the model as a free-form nudge
    (e.g. ``"hyperfine JSON"`` or ``"custom internal CSV with
    mean/stddev columns"``) — optional, but improves accuracy on
    ambiguous inputs.

    Raises ``RuntimeError`` if the model returns malformed JSON;
    raises ``anthropic.APIError`` on network/auth problems.
    """
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError(
            "llm_anthropic requires the `anthropic` package: "
            "pip install anthropic"
        ) from exc

    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set; pass api_key= or export the env var."
        )

    client = anthropic.Anthropic(api_key=key)

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                # Cache the schema + examples — the expensive part of
                # the prompt rarely changes across parse() calls.
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": build_user_prompt(content, format_hint=format_hint),
            }
        ],
    )

    # Extract the text block from the response. Messages API returns
    # a list of content blocks; we expect one text block with the JSON.
    text = "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()

    # Strip possible markdown code fences if the model slipped up.
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop opening fence line (possibly with language tag) and
        # closing fence line.
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"LLM returned non-JSON output: {text[:200]}..."
        ) from exc

    if not isinstance(result, list):
        raise RuntimeError(
            f"LLM returned non-array top level: {type(result).__name__}"
        )

    return result
