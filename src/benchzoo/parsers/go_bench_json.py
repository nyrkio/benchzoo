"""Parser for ``go test -json`` line-delimited output.

``go test -json`` emits one JSON object per line, each representing a
test event. Objects look roughly like::

    {
      "Time":    "2026-04-12T07:13:10.698Z",
      "Action":  "output",
      "Package": "github.com/foo/bar",
      "Test":    "BenchmarkBenchmark1",
      "Output":  "BenchmarkBenchmark1-2   \\t       1\\t2150387943 ns/op\\t..."
    }

Empirically (Go 1.22), benchmark measurements do **not** arrive as
``Action: "bench"`` events — they arrive as ordinary ``Action: "output"``
events whose ``Output`` string is exactly the line that ``go test
-bench`` would print to stdout. So this parser filters to ``Output``
events and delegates line parsing to the same regex used by the text
parser.

``Action: "fail"`` events on a specific ``Test`` flip ``passed`` to
``False`` for the matching benchmark.
"""

from __future__ import annotations

import json

from . import go_bench_text


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    # Collect Output strings (the bench-result lines are in here) and
    # remember which Tests reported a fail action.
    output_lines: list[str] = []
    failed: set[str] = set()

    for raw in content.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            evt = json.loads(raw)
        except json.JSONDecodeError:
            continue

        action = evt.get("Action")
        if action == "output":
            out = evt.get("Output")
            if isinstance(out, str):
                # Strip trailing newline; splitlines below on each call
                # would also work, but Output is a single line here.
                output_lines.append(out.rstrip("\n"))
        elif action == "fail":
            test = evt.get("Test")
            if test:
                failed.add(test)

    results = go_bench_text._parse_lines(output_lines)

    # Apply fail events: match the Go function name (BenchmarkBenchmarkN)
    # back to the test_name slug.
    if failed:
        for func_name in failed:
            slug = go_bench_text._func_to_test_name(func_name)
            for d in results:
                if d["attributes"]["test_name"] == slug:
                    d["passed"] = False

    return results
