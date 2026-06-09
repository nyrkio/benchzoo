"""Parser for JMH's rich human-readable stdout (``output.txt`` / CI log).

JMH prints a running narrative to stdout while it benchmarks, and for
each ``@Benchmark`` method emits a ``Result`` block::

    Result "io.nyrkio.benchzoo.jmh.SampleBenchmark.benchmark1":
      2150.108 ±(99.9%) 0.111 ms/op [Average]
      (min, avg, max) = (2150.101, 2150.108, 2150.114), stdev = 0.006
      CI (99.9%): [2149.996, 2150.219] (assumes normal distribution)

We anchor on the ``Result "<fully-qualified-name>":`` line and read the
**next non-empty line** for the score, error, and unit — the same
"find an anchor line, then read the neighbouring line" strategy the
criterion text parser uses. Anchoring on ``Result`` (rather than the
trailing summary table) buys us the full fully-qualified benchmark name
(the summary table truncates it to ``SampleBenchmark.benchmarkN``) and
the per-result error value.

Two JMH quirks are handled:

1. **Sub-resolution benchmarks** print ``≈ 10⁻⁴ ms/op`` instead of a
   real number — JMH's way of saying "below measurement resolution"
   (our ``benchmark2``, a 0..1000 loop, lands here). The ``10`` and the
   exponent use Unicode superscript digits. We parse the superscript
   exponent and report the magnitude (e.g. ``1e-4 ms/op``) so the
   benchmark is present and non-zero rather than dropped; the score is
   approximate by JMH's own admission.
2. **GitHub-Actions log timestamps.** When captured from a job *log*
   rather than the uploaded artifact, every line is prefixed with an
   ISO-8601 timestamp. We strip it (and ANSI codes) before matching.

The ``avgt`` / ``thrpt`` / ``sample`` / ``ss`` mode determines the
metric direction; the rich text doesn't repeat the mode on the Result
line, so we read it from the ``# Benchmark mode:`` header that precedes
each block (defaulting to ``avgt`` → lower-is-better, matching JMH's
own default and our sample suite).

See ``frameworks/language/jmh/README.md``.
"""

from __future__ import annotations

import re


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Optional GitHub-Actions per-line ISO-8601 timestamp prefix.
_TS = r"(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+)?"

# A "Result" block header carrying the fully-qualified benchmark name.
_RESULT_RE = re.compile(r'^\s*' + _TS + r'Result "([^"]+)":\s*$')

# The score line for a measurable benchmark, e.g.
#   "  2150.108 ±(99.9%) 0.111 ms/op [Average]"
# The "±(<conf>) <error>" middle part is optional (single-shot results
# and degenerate cases omit it). Unit is "<num>/op" or "ops/<unit>" etc.
_SCORE_RE = re.compile(
    r'^\s*' + _TS +
    r'([0-9]+(?:\.[0-9]+)?)'                              # score
    r'(?:\s*±\([^)]*\)\s*([0-9]+(?:\.[0-9]+)?))?'         # optional error
    r'\s+(\S+/op|ops/\S+|\S+/s)\b'                        # unit
)

# The sub-resolution placeholder, e.g. "  ≈ 10⁻⁴ ms/op". The exponent is
# written with Unicode superscript digits and an optional superscript minus.
_APPROX_RE = re.compile(
    r'^\s*' + _TS + r'≈\s*10([⁰-⁹¹²³⁻]+)\s+(\S+/op|ops/\S+|\S+/s)\b'
)

# Header line that tells us the benchmark mode for the following block.
_MODE_RE = re.compile(r'^\s*' + _TS + r'#\s*Benchmark mode:\s*(.+?)\s*$')

_SUPERSCRIPT = {
    "⁰": "0", "¹": "1", "²": "2", "³": "3",
    "⁴": "4", "⁵": "5", "⁶": "6", "⁷": "7",
    "⁸": "8", "⁹": "9", "⁻": "-",
}

# Map JMH's "# Benchmark mode:" human label to direction. Time-per-op
# modes are lower-is-better; throughput is higher-is-better.
_THROUGHPUT_LABELS = ("throughput",)


def _superscript_to_int(s: str) -> int:
    return int("".join(_SUPERSCRIPT.get(ch, "") for ch in s))


def _short_name(fqn: str) -> str:
    return fqn.rsplit(".", 1)[-1]


def _direction_for_unit(unit: str, mode_label: str | None) -> str:
    """Prefer the explicit mode header; fall back to the unit shape."""
    if mode_label and any(t in mode_label.lower() for t in _THROUGHPUT_LABELS):
        return "higher_is_better"
    if mode_label:
        return "lower_is_better"
    # No header seen (a bare Result block): infer from the unit. JMH
    # throughput units are "ops/<time>"; everything else ("<time>/op") is
    # a duration.
    if unit.startswith("ops/"):
        return "higher_is_better"
    return "lower_is_better"


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    lines = [_ANSI_RE.sub("", ln) for ln in content.splitlines()]

    out: list[dict] = []
    current_mode: str | None = None

    for i, line in enumerate(lines):
        mode_m = _MODE_RE.match(line)
        if mode_m:
            current_mode = mode_m.group(1)
            continue

        rm = _RESULT_RE.match(line)
        if not rm:
            continue
        fqn = rm.group(1)

        # Read the next non-empty line for the score.
        score = error = None
        unit = None
        for j in range(i + 1, min(len(lines), i + 4)):
            cand = lines[j]
            if not cand.strip():
                continue
            sm = _SCORE_RE.match(cand)
            if sm:
                score = float(sm.group(1))
                error = float(sm.group(2)) if sm.group(2) else None
                unit = sm.group(3)
                break
            am = _APPROX_RE.match(cand)
            if am:
                exponent = _superscript_to_int(am.group(1))
                score = float(f"1e{exponent}")
                unit = am.group(2)
                break
            # Some other text where we expected a score — give up on this
            # Result block rather than mis-reading.
            break

        if score is None or unit is None:
            continue

        direction = _direction_for_unit(unit, current_mode)

        metrics = [{
            "name": "score", "unit": unit, "value": score,
            "direction": direction,
        }]
        if error is not None:
            metrics.append({
                "name": "score_error", "unit": unit, "value": error,
                "direction": direction,
            })

        test: dict = {"test_name": _short_name(fqn)}
        if "." in fqn:
            test["group"] = fqn.rsplit(".", 1)[0]

        out.append({
            "test": test,
            "run": {"passed": True},
            "env": {"framework": {"name": "jmh"}},
            "metrics": metrics,
        })

    return out
