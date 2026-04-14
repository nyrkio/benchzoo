"""Parser for bash's builtin ``time`` keyword output.

The bash builtin prints exactly three lines to stderr after the timed
command finishes::

    real    0m2.155s
    user    0m0.001s
    sys     0m0.001s

``run.sh`` in ``frameworks/generic/time`` wraps each benchmark's output
with plain-text separators so blocks can be keyed to a test name::

    === benchmark1 (bash builtin time) ===
    ...
    real    0m2.153s
    user    0m0.001s
    sys     0m0.002s
    === end benchmark1 ===

Durations are formatted as ``<Xm>Y.ZZZs`` where ``X`` is minutes and
``Y.ZZZ`` is seconds; the parser converts to total seconds.

See ``frameworks/generic/time/README.md`` for the parser notes this
implementation follows.
"""

from __future__ import annotations

import re


_HEADER_RE = re.compile(r"^===\s+(\S+)\s+\(bash builtin time\)\s+===\s*$")
_END_RE = re.compile(r"^===\s+end\s+(\S+)\s+===\s*$")
_TIME_RE = re.compile(r"^(real|user|sys)\s+(\d+)m([\d.]+)s\s*$")


def _to_seconds(minutes: str, seconds: str) -> float:
    return int(minutes) * 60 + float(seconds)


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    out: list[dict] = []
    current_name: str | None = None
    current_times: dict[str, float] = {}

    for line in content.splitlines():
        header = _HEADER_RE.match(line)
        if header:
            current_name = header.group(1)
            current_times = {}
            continue

        if _END_RE.match(line):
            if current_name is not None and current_times:
                metrics = []
                for label in ("real", "user", "sys"):
                    if label in current_times:
                        metrics.append({
                            "name": label,
                            "unit": "s",
                            "value": current_times[label],
                            "direction": "lower_is_better",
                        })
                out.append({
                    "test": {"test_name": current_name},
                    "run": {"passed": True},
                    "env": {"framework": {"name": "time"}},
                    "metrics": metrics,
                })
            current_name = None
            current_times = {}
            continue

        if current_name is None:
            continue

        m = _TIME_RE.match(line)
        if m:
            label, minutes, seconds = m.group(1), m.group(2), m.group(3)
            current_times[label] = _to_seconds(minutes, seconds)

    return out
