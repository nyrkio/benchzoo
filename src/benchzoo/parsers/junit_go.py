"""Parser for gotestsum's junit XML output.

Per-producer junit parser. gotestsum emits testcase names as the Go
test function name verbatim (e.g. ``TestBenchmark1``). We strip the
``Test`` prefix and lowercase the remainder (``benchmark1``) so
test_name matches the canonical corpus naming.

See ``frameworks/unit-or-qa/junit-go/README.md``.
"""

from __future__ import annotations

from benchzoo.parsers._junit_common import parse_junit


def _normalize(name: str) -> str:
    # gotestsum sometimes produces names like "TestBenchmark1" or
    # "Test-Suite/TestBenchmark1". We take the last path segment and
    # strip "Test" prefix.
    tail = name.rsplit("/", 1)[-1]
    if tail.startswith("Test"):
        tail = tail[4:]
    return tail[:1].lower() + tail[1:] if tail else tail


def parse(content: bytes | str) -> list[dict]:
    return parse_junit(content, framework_name="junit-go", normalize_name=_normalize)
