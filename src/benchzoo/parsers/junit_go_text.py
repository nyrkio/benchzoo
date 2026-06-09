"""Parser for ``go test`` verbose stdout (as wrapped by gotestsum).

The junit-go framework runs the canonical sample benchmark as ordinary
``go test`` unit tests wrapped by ``gotestsum --format=standard-verbose``
(see ``frameworks/unit-or-qa/junit-go/run.sh``). The primary artifact is
JUnit XML (parsed by :mod:`junit_go`), but ``standard-verbose`` ALSO tees
Go's own per-test verbose log to stdout — which is the only thing that
survives when no artifact is uploaded and we read the CI job log::

    === RUN   TestBenchmark1
    --- PASS: TestBenchmark1 (2.15s)
    === RUN   TestBenchmark2
    --- PASS: TestBenchmark2 (0.00s)
    ...
    --- PASS: TestBenchmark4 (1.15s)
    PASS
    ok  	github.com/nyrkio/benchzoo/...	3.305s

We scan for the ``--- PASS/FAIL/SKIP: <Name> (<n>s)`` result lines — Go's
standard ``testing`` verbose format. Each carries the per-test wall-clock
duration in seconds with two decimals (Go truncates here, so the
sub-millisecond benchmark2/benchmark3 legitimately read ``0.00s`` — the
honest value this format can express; the richer XML ``time`` attribute is
likewise ``0.000000`` for them).

Name normalization mirrors :mod:`junit_go`: ``TestBenchmark1`` →
``benchmark1`` (strip the ``Test`` prefix Go's convention requires,
lowercase the leading char).

In CI the lines may be prefixed with GitHub Actions' ISO-8601 timestamp
(when read from a job log rather than a clean artifact) and may carry ANSI
color from gotestsum; both are tolerated.
"""

from __future__ import annotations

import re


# Strip ANSI escapes (gotestsum colorizes its live log).
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Optional GitHub-Actions per-line ISO-8601 timestamp prefix (present when
# the output is read from a job *log*; clean artifacts have none).
_TS = r"(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+)?"

# Go's standard `testing` verbose result line:
#   "--- PASS: TestBenchmark1 (2.15s)"
# The status is PASS / FAIL / SKIP; the name is the Go test function name;
# the parenthesised value is the wall-clock duration in seconds.
_RESULT_RE = re.compile(
    r"^\s*" + _TS + r"---\s+(?P<status>PASS|FAIL|SKIP):\s+"
    r"(?P<name>\S+)\s+\(\s*([0-9.]+)s\s*\)"
)


def _normalize(name: str) -> str:
    # Subtests come as "TestParent/sub"; take the last path segment. Then
    # strip the Go-mandated "Test" prefix and lowercase the leading char,
    # matching the junit_go XML parser's naming.
    tail = name.rsplit("/", 1)[-1]
    if tail.startswith("Test"):
        tail = tail[4:]
    return (tail[:1].lower() + tail[1:]) if tail else tail


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    out: list[dict] = []
    for raw in content.splitlines():
        m = _RESULT_RE.match(_ANSI_RE.sub("", raw))
        if not m:
            continue
        name = _normalize(m.group("name"))
        if not name:
            continue
        seconds = float(m.group(3))
        passed = m.group("status") != "FAIL"
        out.append({
            "test": {"test_name": name},
            "run": {"passed": passed},
            "env": {"framework": {"name": "junit-go"}},
            "metrics": [
                {"name": "duration", "unit": "s", "value": seconds,
                 "direction": "lower_is_better"},
            ],
        })
    return out
