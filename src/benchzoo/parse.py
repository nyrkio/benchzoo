"""End-to-end parse orchestration: deterministic parsers first, LLM fallback.

The sniffer + per-framework parsers handle the formats benchzoo knows.
When they can't — an unrecognised format, or one too noisy to sniff (e.g.
a CI ``output.txt`` that's mostly compiler output with the benchmark
results buried inside) — :func:`parse` falls back to the LLM parsers:
local Ollama first, then the Anthropic API, whichever is reachable.

This is the single entry point a caller should use when it just wants
"turn this benchmark output into Nyrkiö rows, however you can". The
deterministic path stays cheap and never-wrong; the LLM is opt-in muscle
for the long tail. Detection (:func:`benchzoo.sniff`) deliberately stays
separate and LLM-free — see its docstring.
"""
from __future__ import annotations

import logging

from benchzoo.sniff import sniff
from benchzoo.parsers import find_parser

LOG = logging.getLogger("benchzoo.parse")


def llm_parse(content, *, format_hint=None):
    """Try the LLM fallback parsers in order: local Ollama, then Anthropic.

    Each backend is best-effort: if it isn't configured/reachable, or it
    fails to produce rows, we move on to the next. Returns ``[]`` if none
    succeed — never raises just because a backend is unavailable.

    ``format_hint`` is passed through to the model as a free-form nudge
    (e.g. the framework name sniff *suspected* but couldn't dispatch)."""
    from benchzoo.parsers import llm_local, llm_anthropic
    for backend in (llm_local, llm_anthropic):
        name = backend.__name__.rsplit(".", 1)[-1]
        try:
            rows = backend.parse(content, format_hint=format_hint)
        except Exception as e:
            LOG.info("LLM fallback %s unavailable/failed: %s", name, e)
            continue
        if rows:
            LOG.info("LLM fallback %s parsed %d row(s)", name, len(rows))
            return rows
    return []


def parse(content, *, framework=None, fmt=None, use_llm=True):
    """Parse benchmark output into Nyrkiö-shaped rows, end to end.

    Resolution order:
      1. explicit ``framework``/``fmt``, else :func:`sniff` the content;
      2. dispatch to the matching deterministic parser;
      3. if that yields no rows (unknown format, empty result, or a
         parser error) and ``use_llm`` is set, fall back to
         :func:`llm_parse`.

    Returns ``[]`` when nothing can parse it. Only raises on misuse
    (e.g. an explicit unknown ``framework``), never on "couldn't parse
    this content"."""
    spec = None
    if framework is None:
        spec = sniff(content)
        if spec:
            framework, _, sniffed_fmt = spec.partition("/")
            fmt = fmt or (sniffed_fmt or None)
    if framework:
        try:
            rows = find_parser(framework, fmt).parse(content)
            if rows:
                return rows
        except Exception as e:
            LOG.info("deterministic parse (%s/%s) produced nothing: %s",
                     framework, fmt, e)
    if use_llm:
        return llm_parse(content, format_hint=spec)
    return []
