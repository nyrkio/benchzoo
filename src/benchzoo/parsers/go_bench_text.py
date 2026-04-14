"""Parser for ``go test -bench`` default text output.

Each benchmark emits one line of the form::

    BenchmarkName-cpus   N   X ns/op   [Y B/op   Z allocs/op]

where ``BenchmarkName`` is the Go function name (e.g.
``BenchmarkBenchmark1``) and ``-cpus`` is a ``GOMAXPROCS`` suffix. The
parser strips the leading ``Benchmark`` prefix and lowercases the
remainder to form ``attributes["test_name"]`` — for the canonical suite
that yields ``benchmark1`` .. ``benchmark4``.

Other lines in the stream (``goos:``, ``goarch:``, ``pkg:``, ``cpu:``
preamble, ``PASS``/``FAIL``/``ok`` footer, and ``b.Logf`` output) are
ignored for the purposes of per-benchmark results. A ``FAIL`` line
naming a specific benchmark flips ``passed`` to ``False`` for that test.

See ``frameworks/language/go-test-bench/README.md`` for the parser notes
this implementation follows.
"""

from __future__ import annotations

import re


# BenchmarkName-cpus \t N \t X ns/op [\t Y B/op \t Z allocs/op]
_BENCH_RE = re.compile(
    r"^(?P<name>Benchmark[^\s-]+)(?:-(?P<cpus>\d+))?\s+"
    r"(?P<iters>\d+)\s+"
    r"(?P<ns>[\d.]+)\s+ns/op"
    r"(?:\s+(?P<bytes>[\d.]+)\s+B/op)?"
    r"(?:\s+(?P<allocs>[\d.]+)\s+allocs/op)?"
)

_FAIL_RE = re.compile(r"^--- FAIL:\s+(?P<name>Benchmark\S+?)(?:-\d+)?\b")


def _func_to_test_name(func_name: str) -> str:
    # "BenchmarkBenchmark1" -> "benchmark1"
    stripped = func_name[len("Benchmark"):] if func_name.startswith("Benchmark") else func_name
    return stripped.lower()


def _parse_lines(lines):
    """Shared line-based parsing used by both text and JSON parsers."""
    results: list[dict] = []
    by_name: dict[str, dict] = {}

    for line in lines:
        line = line.rstrip("\n").rstrip("\r")
        if not line:
            continue

        m = _BENCH_RE.match(line.strip())
        if m:
            func_name = m.group("name")
            test_name = _func_to_test_name(func_name)
            ns = float(m.group("ns"))
            metrics = [
                {
                    "name": "ns_per_op",
                    "unit": "ns",
                    "value": ns,
                    "direction": "lower_is_better",
                },
            ]
            if m.group("bytes") is not None:
                metrics.append({
                    "name": "bytes_per_op",
                    "unit": "B",
                    "value": float(m.group("bytes")),
                    "direction": "lower_is_better",
                })
            if m.group("allocs") is not None:
                metrics.append({
                    "name": "allocs_per_op",
                    "unit": "count",
                    "value": float(m.group("allocs")),
                    "direction": "lower_is_better",
                })

            d = {
                "test": {"test_name": test_name},
                "run": {"passed": True},
                "env": {"framework": {"name": "go-test-bench"}},
                "metrics": metrics,
            }
            results.append(d)
            by_name[func_name] = d
            continue

        fm = _FAIL_RE.match(line.strip())
        if fm:
            func_name = fm.group("name")
            if func_name in by_name:
                by_name[func_name]["run"]["passed"] = False

    return results


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    return _parse_lines(content.splitlines())
