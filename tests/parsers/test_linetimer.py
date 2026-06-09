"""Ground-truth tests for the linetimer parser.

linetimer's ``CodeTimer`` prints ``Code block 'NAME' took: <n> <unit>``
per timed block (default unit: milliseconds; callers may override, e.g.
``pola-rs/polars-benchmark`` uses seconds). In CI these lines arrive
either prefixed with GitHub Actions' ISO-8601 timestamp (read from a job
*log*, no artifact — polars' case) or clean (from an artifact). Both must
parse, and units normalise to seconds.

``test_four_sample_benchmarks_round_trip`` runs the same four blocks as
the ``frameworks/language/linetimer`` example through *real* linetimer and
parses the captured stdout — no fixture, no throwaway script.
"""

from __future__ import annotations

import time

import pytest

from benchzoo.parsers import find_parser, linetimer
from benchzoo.sniff import sniff

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


def test_sniff_identifies_timestamped_log():
    assert sniff(_LOG) == "linetimer/text"


def test_parses_timestamped_log():
    r = _by_name(linetimer.parse(_LOG))
    assert set(r) == {"Run polars query 1", "Run polars query 2"}
    m = _metric(r["Run polars query 1"])
    assert m["value"] == pytest.approx(1.50120)
    assert m["unit"] == "s"
    assert m["direction"] == "lower_is_better"
    assert r["Run polars query 1"]["env"]["framework"]["name"] == "linetimer"
    assert r["Run polars query 1"]["run"]["passed"] is True


def test_parses_clean_artifact_form_and_normalises_units():
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


def test_four_sample_benchmarks_round_trip(capsys):
    """Run the four sample CodeTimer blocks (same as the
    ``frameworks/language/linetimer`` example) through real linetimer,
    capture stdout, and parse it. All four must round-trip with
    seconds-normalised, lower-is-better timings.
    """
    lt = pytest.importorskip("linetimer")

    with lt.CodeTimer("benchmark1"):
        time.sleep(0.05)
    with lt.CodeTimer("benchmark2"):
        time.sleep(0.10)
    with lt.CodeTimer("benchmark3"):
        time.sleep(0.15)
    with lt.CodeTimer("benchmark4", unit="s"):   # seconds, like polars
        time.sleep(0.20)

    rows = linetimer.parse(capsys.readouterr().out)
    by = _by_name(rows)
    assert set(by) == {"benchmark1", "benchmark2", "benchmark3", "benchmark4"}

    # Defaults emit ms; benchmark4 emits s. The parser normalises all to
    # seconds, so each block's value is at least its sleep (CI jitter only
    # makes it longer). Generous upper bound guards against a unit-scaling
    # bug (e.g. ms read as s would be ~1000x off).
    lower = {"benchmark1": 0.03, "benchmark2": 0.07,
             "benchmark3": 0.11, "benchmark4": 0.15}
    for name, row in by.items():
        m = _metric(row)
        assert m["unit"] == "s"
        assert m["direction"] == "lower_is_better"
        assert row["env"]["framework"]["name"] == "linetimer"
        assert lower[name] <= m["value"] <= 5.0, (name, m)
