"""Parser for ``perf stat`` text (default) output.

The default text format is split into per-invocation blocks. Our
``run.sh`` wraps each benchmark's block with
``=== benchmarkN (perf stat, text) ===`` / ``=== end benchmarkN ===``
separators. Each block contains lines like::

     Performance counter stats for './benchmark1.sh':

               2434997      task-clock                       #    0.001 CPUs utilized
                     4      context-switches                 #    1.643 K/sec
                     0      cpu-migrations                   #    0.000 /sec
                   285      page-faults                      #  117.043 K/sec
       <not supported>      cycles

           2.153524563 seconds time elapsed
           0.001176000 seconds user
           0.002117000 seconds sys

The ``<not supported>`` token (or ``<not counted>``) appears when
``kernel.perf_event_paranoid`` blocks access — common on GitHub
Actions runners. The parser emits those counters as ``null``-valued
metrics are elided (we simply skip them rather than fabricate values).

The unambiguous wall-time signal is the ``<X> seconds time elapsed``
line — that's what the ground-truth tests key off.

See ``frameworks/generic/perf-stat/README.md``.
"""

from __future__ import annotations

import re


_HEADER_RE = re.compile(r"^===\s+(\S+)\s+\(perf stat, text\)\s+===\s*$")
_END_RE = re.compile(r"^===\s+end\s+(\S+)\s+===\s*$")

# "2.153524563 seconds time elapsed" (and variants with leading whitespace)
_SECONDS_RE = re.compile(r"^\s*([0-9.]+)\s+seconds\s+(time elapsed|user|sys)\s*$")

# "   2434997      task-clock   ..." / "   <not supported>  cycles  ..."
# We key the integer/float value before the event name; skip if token is
# "<not supported>" or "<not counted>".
_COUNTER_RE = re.compile(
    r"^\s*(?P<value><not supported>|<not counted>|[0-9.,]+)\s+"
    r"(?P<event>[a-zA-Z][a-zA-Z0-9_\-:]*)\b"
)


def _parse_block(test_name: str, lines: list[str]) -> dict:
    metrics: list[dict] = []

    for line in lines:
        m = _SECONDS_RE.match(line)
        if m:
            value = float(m.group(1))
            kind = m.group(2).replace(" ", "_")  # time_elapsed / user / sys
            key = "wall_time" if kind == "time_elapsed" else kind
            metrics.append({
                "name": key,
                "unit": "s",
                "value": value,
                "direction": "lower_is_better",
            })
            continue

        m = _COUNTER_RE.match(line)
        if m:
            raw = m.group("value")
            event = m.group("event")
            if raw.startswith("<"):
                # <not supported> / <not counted> — skip.
                continue
            try:
                value = float(raw.replace(",", ""))
            except ValueError:
                continue
            metrics.append({
                "name": event.replace("-", "_"),
                "unit": "count",
                "value": value,
                "direction": "lower_is_better",
            })

    return {
        "test": {"test_name": test_name},
        "run": {"passed": True},
        "env": {"framework": {"name": "perf-stat"}},
        "metrics": metrics,
    }


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    out: list[dict] = []
    current_name: str | None = None
    current_lines: list[str] = []

    for line in content.splitlines():
        header = _HEADER_RE.match(line)
        if header:
            current_name = header.group(1)
            current_lines = []
            continue

        if _END_RE.match(line):
            if current_name is not None:
                out.append(_parse_block(current_name, current_lines))
            current_name = None
            current_lines = []
            continue

        if current_name is not None:
            current_lines.append(line)

    return out
