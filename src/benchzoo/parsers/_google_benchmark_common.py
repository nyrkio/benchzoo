"""Shared helpers for the three Google Benchmark parsers (json, csv,
text). Kept out of the individual modules so the composite-name
parsing stays in one place — Google Benchmark's naming scheme is
surprisingly detailed and we want to interpret it identically across
output formats.
"""
from __future__ import annotations


def split_benchmark_name(raw: str) -> tuple[str, dict]:
    """Split a Google Benchmark composite name into base + attrs.

    Google Benchmark encodes the benchmark's configured parameters
    into the reported ``name`` by appending ``/``-separated segments.
    Examples from the wild:

    ========================================  =================================
    raw name                                   → base, attrs
    ========================================  =================================
    ``BM_Foo``                                 → ``BM_Foo``, ``{}``
    ``BM_Foo/16``                              → ``BM_Foo``, ``{"args": "16"}``
    ``BM_Foo/16/32``                           → ``BM_Foo``, ``{"args": "16/32"}``
    ``BM_Foo/threads:8``                       → ``BM_Foo``, ``{"threads": 8}``
    ``BM_Foo/16/threads:8``                    → ``BM_Foo``, ``{"args": "16", "threads": 8}``
    ``BM_Foo/iterations:100``                  → ``BM_Foo``, ``{"iterations": 100}``
    ========================================  =================================

    ``args`` is kept as a string (the original ``/``-joined form) so
    callers that want structure can split it themselves, and callers
    that just want to display the parameterisation can show it
    verbatim. ``threads`` and ``iterations`` are returned as ints.

    Any unrecognised ``name:value`` segment is folded back into the
    base so the test stays uniquely addressable — better to preserve
    a name we don't understand than silently collapse two distinct
    benchmarks into one.
    """
    if "/" not in raw:
        return raw, {}
    parts = raw.split("/")
    base = parts[0]
    args: list[str] = []
    attrs: dict = {}
    known_keys = {"threads", "iterations"}
    for seg in parts[1:]:
        if ":" in seg:
            key, _, val = seg.partition(":")
            if key in known_keys:
                try:
                    attrs[key] = int(val)
                    continue
                except ValueError:
                    pass
            # Unknown or unparseable modifier — keep it in the base so
            # we don't collapse distinct runs.
            base = base + "/" + seg
        else:
            args.append(seg)
    if args:
        attrs["args"] = "/".join(args)
    return base, attrs
