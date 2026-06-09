"""Ground-truth tests for the linetimer parser.

linetimer's ``CodeTimer`` prints ``Code block 'NAME' took: <n> <unit>``
per timed block (default unit: milliseconds; callers may override, e.g.
``pola-rs/polars-benchmark`` uses seconds). In CI these lines arrive
either prefixed with GitHub Actions' ISO-8601 timestamp (read from a job
*log*, no artifact — polars' case) or clean (from an artifact). Both must
parse, and units normalise to seconds.

``tests/data/linetimer-output/output.txt`` is the captured native output
of the four canonical benchmarks (``docs/sample-benchmark.md``), produced
by ``frameworks/language/linetimer/bench.py``. The ground-truth test
asserts the known wall times — the load-bearing "does the parser read the
right field" check.
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import find_parser, linetimer
from benchzoo.sniff import sniff

FIXTURES = pathlib.Path(__file__).parent.parent / "data" / "linetimer-output"

# A GitHub-Actions job-log excerpt: per-line ISO timestamp + cargo noise.
_LOG = (
    "2026-06-08T20:48:55.1234567Z    Compiling polars v1.41.2\n"
    "2026-06-08T20:49:01.2345678Z Code block 'Run polars query 1' took: 1.50120 s\n"
    "2026-06-08T20:49:02.3456789Z some unrelated log line\n"
    "2026-06-08T20:49:03.4567890Z Code block 'Run polars query 2' took: 0.07198 s\n"
)


def _by_name(rows):
    return {r["test"]["test_name"]: r for r in rows}


def _metric(row, name="time"):
    for m in row["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"no metric {name!r} in {row}")


def test_registry_resolves():
    assert find_parser("linetimer", "text") is linetimer
    assert find_parser("linetimer") is linetimer  # single format -> fmt optional


# ---------------------------------------------------------------------------
# Ground truth: the four canonical sample benchmarks (docs/sample-benchmark.md)
# ---------------------------------------------------------------------------

def test_canonical_benchmarks_ground_truth():
    rows = linetimer.parse((FIXTURES / "output.txt").read_text())
    by = _by_name(rows)
    assert {"benchmark1", "benchmark2", "benchmark3", "benchmark4"} <= set(by)

    # Every block: seconds-normalised, lower-is-better, framework tagged.
    for name in ("benchmark1", "benchmark2", "benchmark3", "benchmark4"):
        m = _metric(by[name])
        assert m["unit"] == "s"
        assert m["direction"] == "lower_is_better"
        assert by[name]["env"]["framework"]["name"] == "linetimer"
        assert by[name]["run"]["passed"] is True

    # Test 1 — ~2.15 s sleep.
    assert 2.0 < _metric(by["benchmark1"])["value"] < 2.4
    # Test 2 — sub-millisecond CPU loop, but NOT rounded to zero.
    assert 0.0 < _metric(by["benchmark2"])["value"] < 0.05
    # Test 3 — 1.4 MB to /dev/null: sub-ms to a few ms.
    assert 0.0 < _metric(by["benchmark3"])["value"] < 0.1
    # Test 4 — change-detection showcase: one of {1.15, 2.15, 3.15} s
    # depending on the capture month (loose check per the spec).
    v4 = _metric(by["benchmark4"])["value"]
    assert any(abs(v4 - t) < 0.25 for t in (1.15, 2.15, 3.15)), v4


# ---------------------------------------------------------------------------
# Format handling: GH-log timestamp prefix, unit normalisation, edge cases
# ---------------------------------------------------------------------------

def test_sniff_identifies_timestamped_log():
    assert sniff(_LOG) == "linetimer/text"


def test_parses_timestamped_log():
    r = _by_name(linetimer.parse(_LOG))
    assert set(r) == {"Run polars query 1", "Run polars query 2"}
    m = _metric(r["Run polars query 1"])
    assert m["value"] == pytest.approx(1.50120)
    assert m["unit"] == "s"


def test_normalises_units_to_seconds():
    rows = linetimer.parse(
        "Code block 'a' took: 0.5 s\n"
        "Code block 'b' took: 1250 ms\n"     # linetimer's DEFAULT unit
        "Code block 'c' took: 2 min\n"
    )
    vals = {r["test"]["test_name"]: _metric(r)["value"] for r in rows}
    assert vals["a"] == pytest.approx(0.5)
    assert vals["b"] == pytest.approx(1.25)    # ms -> s
    assert vals["c"] == pytest.approx(120.0)   # min -> s


def test_ignores_anonymous_and_non_took_lines():
    rows = linetimer.parse(
        "Code block took: 1.0 s\n"            # anonymous (no quotes) -> skipped
        "random thing took: 5 s\n"            # not a Code block line
        "Code block 'kept' took: 3.0 s\n"
    )
    assert [r["test"]["test_name"] for r in rows] == ["kept"]
