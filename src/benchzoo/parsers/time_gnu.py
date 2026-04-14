"""Parser for GNU ``/usr/bin/time -v`` verbose output.

The ``-v`` format is a fixed multi-line block of ``Label: value`` pairs.
``run.sh`` in ``frameworks/generic/time`` wraps each benchmark's output
with plain-text separators so blocks can be keyed to a test name::

    === benchmark1 (/usr/bin/time -v) ===
        Command being timed: "./benchmark1.sh"
        User time (seconds): 0.00
        System time (seconds): 0.00
        Percent of CPU this job got: 0%
        Elapsed (wall clock) time (h:mm:ss or m:ss): 0:02.15
        ...
        Exit status: 0
    === end benchmark1 ===

See ``frameworks/generic/time/README.md`` for the parser notes this
implementation follows.
"""

from __future__ import annotations

import re


_HEADER_RE = re.compile(r"^===\s+(\S+)\s+\(/usr/bin/time -v\)\s+===\s*$")
_END_RE = re.compile(r"^===\s+end\s+(\S+)\s+===\s*$")
# GNU time labels can contain colons (e.g.
# "Elapsed (wall clock) time (h:mm:ss or m:ss): 0:02.15"), so we split
# on the first ": " (colon-space) — that is the field separator, while
# colons inside the label or value (like h:mm:ss) are never followed by
# a space in GNU time's format.


def _elapsed_to_seconds(value: str) -> float:
    """Convert ``h:mm:ss.ff`` or ``m:ss.ff`` to total seconds."""
    parts = value.strip().split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    if len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return float(value)


def _parse_block(name: str, fields: dict[str, str]) -> dict:
    metrics: list[dict] = []

    if "Elapsed (wall clock) time (h:mm:ss or m:ss)" in fields:
        metrics.append({
            "name": "elapsed",
            "unit": "s",
            "value": _elapsed_to_seconds(fields["Elapsed (wall clock) time (h:mm:ss or m:ss)"]),
            "direction": "lower_is_better",
        })

    if "User time (seconds)" in fields:
        metrics.append({
            "name": "user",
            "unit": "s",
            "value": float(fields["User time (seconds)"]),
            "direction": "lower_is_better",
        })

    if "System time (seconds)" in fields:
        metrics.append({
            "name": "system",
            "unit": "s",
            "value": float(fields["System time (seconds)"]),
            "direction": "lower_is_better",
        })

    if "Percent of CPU this job got" in fields:
        raw = fields["Percent of CPU this job got"].rstrip("%")
        metrics.append({
            "name": "cpu_percent",
            "unit": "%",
            "value": float(raw),
            # no direction: higher CPU% can mean less I/O wait OR more work packed in;
            # not universally better or worse.
        })

    if "Maximum resident set size (kbytes)" in fields:
        metrics.append({
            "name": "max_rss",
            "unit": "kB",
            "value": int(fields["Maximum resident set size (kbytes)"]),
            "direction": "lower_is_better",
        })

    if "Major (requiring I/O) page faults" in fields:
        metrics.append({
            "name": "page_faults_major",
            "unit": "count",
            "value": int(fields["Major (requiring I/O) page faults"]),
            "direction": "lower_is_better",
        })

    if "Minor (reclaiming a frame) page faults" in fields:
        metrics.append({
            "name": "page_faults_minor",
            "unit": "count",
            "value": int(fields["Minor (reclaiming a frame) page faults"]),
            "direction": "lower_is_better",
        })

    if "Voluntary context switches" in fields:
        metrics.append({
            "name": "voluntary_context_switches",
            "unit": "count",
            "value": int(fields["Voluntary context switches"]),
            "direction": "lower_is_better",
        })

    if "Involuntary context switches" in fields:
        metrics.append({
            "name": "involuntary_context_switches",
            "unit": "count",
            "value": int(fields["Involuntary context switches"]),
            "direction": "lower_is_better",
        })

    exit_status = 0
    if "Exit status" in fields:
        exit_status = int(fields["Exit status"])
        metrics.append({
            "name": "exit_status",
            "unit": "count",
            "value": exit_status,
        })

    return {
        "test": {"test_name": name},
        "run": {"passed": exit_status == 0},
        "env": {"framework": {"name": "time"}},
        "metrics": metrics,
    }


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    out: list[dict] = []
    current_name: str | None = None
    current_fields: dict[str, str] = {}

    for line in content.splitlines():
        header = _HEADER_RE.match(line)
        if header:
            current_name = header.group(1)
            current_fields = {}
            continue

        if _END_RE.match(line):
            if current_name is not None and current_fields:
                out.append(_parse_block(current_name, current_fields))
            current_name = None
            current_fields = {}
            continue

        if current_name is None:
            continue

        stripped = line.lstrip()
        if ": " in stripped:
            key, _, value = stripped.partition(": ")
            current_fields[key.strip()] = value.strip()

    return out
