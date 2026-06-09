"""Parser for BenchmarkTools.jl's human-readable stdout summary.

The benchzoo sample (``frameworks/language/benchmarktools-jl/bench.jl``)
runs the suite and then prints a one-line-per-benchmark summary using
Julia's ``Trial`` show method::

    --- results summary ---
    benchmark1: Trial(2.153 s)
    benchmark2: Trial(20.000 ns)
    benchmark3: Trial(25.739 μs)
    benchmark4: Trial(1.152 s)
    --- wrote output.json ---

Each ``Trial(<value> <unit>)`` reports the *minimum* sample time, which
is BenchmarkTools' default summary statistic. The unit auto-scales per
benchmark (``ns`` / ``μs`` / ``ms`` / ``s``), so a value is meaningless
without its unit — we normalise everything to **seconds**.

Why a text parser when ``output.json`` exists? When a Julia project
prints its BenchmarkTools results to a CI log without uploading the JSON
artifact, this is the only thing benchzoo can read. The lines are buried
in BenchmarkTools' verbose progress chatter ("(1/4) benchmarking ...",
"done (took ... seconds)") and — when captured from a GitHub Actions log
— carry an ISO-8601 timestamp prefix. We scan the whole content for the
``Trial(...)`` anchor and ignore everything else.

The micro symbol may be the Greek mu (U+03BC, what Julia emits) or the
micro sign (U+00B5); we also accept ASCII ``us`` defensively.

See ``frameworks/language/benchmarktools-jl/README.md``.
"""

from __future__ import annotations

import re


# Strip ANSI escape codes defensively (Julia can colorize ``@info`` etc.).
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Seconds per BenchmarkTools time unit. Julia's `prettytime` emits one of
# ns / μs / ms / s; μ is Greek mu (U+03BC) but accept the micro sign and
# ASCII "us" too.
_UNIT_S = {"ns": 1e-9, "µs": 1e-6, "μs": 1e-6, "us": 1e-6, "ms": 1e-3, "s": 1.0}
_UNIT = r"(?:ns|µs|μs|us|ms|s)"

# A summary line: "<name>: Trial(<value> <unit>)". The name is whatever
# precedes the colon; the bench keys in the canonical suite are
# benchmark1..benchmark4 but we don't hard-code them. Tolerate a leading
# GitHub-Actions ISO-8601 timestamp prefix by anchoring on the colon +
# "Trial(" rather than the start of the line.
_TRIAL_RE = re.compile(
    r"(?P<name>\S[^:]*?)\s*:\s*Trial\(\s*"
    r"(?P<value>[0-9][0-9.]*)\s*(?P<unit>" + _UNIT + r")\s*\)"
)


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    out: list[dict] = []
    for raw in content.splitlines():
        line = _ANSI_RE.sub("", raw)
        m = _TRIAL_RE.search(line)
        if not m:
            continue
        name = m.group("name").strip()
        # Drop any leading GH-log ISO timestamp that got swept into the
        # name capture (e.g. "2026-06-04T03:57:17.3765775Z benchmark1").
        name = name.rsplit("Z ", 1)[-1].strip() if "Z " in name else name
        name = name.split()[-1] if " " in name else name
        if not name:
            continue
        value_s = float(m.group("value")) * _UNIT_S[m.group("unit")]
        out.append({
            "test": {"test_name": name},
            "run": {"passed": True},
            "env": {"framework": {"name": "benchmarktools-jl"}},
            "metrics": [
                {"name": "time", "unit": "s", "value": value_s,
                 "direction": "lower_is_better"},
            ],
        })
    return out
