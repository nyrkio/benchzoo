"""Ground-truth tests for the memtier_benchmark text (stdout) parser.

memtier_benchmark prints an ``ALL STATS`` table — one row per operation
type (``Sets``, ``Gets``, ``Waits``, ``Totals``) with columns keyed by
header name (``Ops/sec``, ``Hits/sec``, ``Misses/sec``, ``Avg. Latency``,
percentile latencies, ``KB/sec``). The benchzoo memtier framework
deviates from the canonical four-benchmark shape (no 2.15 s sleeps): each
operation row becomes a ``test_name``, so the ground-truth assertions key
off memtier's own characteristic numbers, not benchmark1..4.

``tests/data/memtier-output/output-text.txt`` is a real slice of the
memtier CI job *log* (run 24319572678): per-line ISO-8601 timestamp
prefix, the ``[RUN #1 …]`` progress lines, the ``ALL STATS`` table, and
the start of the latency-distribution histogram (whose own ``Type  <=
msec  Percent`` header must NOT be mistaken for the stats header). The
parser must find the table amid that noise and tolerate the timestamps.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from benchzoo.parsers import find_parser, memtier_text
from benchzoo.sniff import sniff

FIXTURES = pathlib.Path(__file__).parent.parent / "data" / "memtier-output"


def _by_name(rows):
    return {r["test"]["test_name"]: r for r in rows}


def _metric(row, name):
    for m in row["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"no metric {name!r} in {row}")


def test_registry_resolves():
    # The ("memtier","text") -> "memtier_text" registry entry is merged
    # centrally (this subagent does not edit the shared __init__.py). Once
    # present, find_parser must resolve to this module; until then, skip
    # rather than fail on the pending merge.
    try:
        resolved = find_parser("memtier", "text")
    except (KeyError, ValueError):
        pytest.skip("memtier/text registry entry not yet merged")
    assert resolved is memtier_text


# ---------------------------------------------------------------------------
# Ground truth: memtier's own ALL STATS numbers from the real CI log slice.
# (memtier deviates from the canonical benchmark1..4 shape — see README.)
# ---------------------------------------------------------------------------

def test_all_stats_ground_truth():
    rows = memtier_text.parse((FIXTURES / "output-text.txt").read_text())
    by = _by_name(rows)

    # One row per operation type printed in the table.
    assert {"sets", "gets", "waits", "totals"} <= set(by)

    # Every row: framework tagged, passed.
    for name in ("sets", "gets", "totals"):
        assert by[name]["env"]["framework"]["name"] == "memtier"
        assert by[name]["run"]["passed"] is True

    # Throughput band: localhost Redis, 20 clients -> tens of thousands ops/s.
    sets_ops = _metric(by["sets"], "ops_per_sec")
    assert sets_ops["unit"] == "ops/s"
    assert sets_ops["direction"] == "higher_is_better"
    assert 10_000 < sets_ops["value"] < 200_000          # 27127.17
    assert sets_ops["value"] == pytest.approx(27127.17)

    gets_ops = _metric(by["gets"], "ops_per_sec")["value"]
    assert gets_ops == pytest.approx(27125.17)

    # Totals ops/sec is Sets + Gets (combined throughput).
    totals_ops = _metric(by["totals"], "ops_per_sec")["value"]
    assert totals_ops == pytest.approx(54252.34)
    assert totals_ops == pytest.approx(sets_ops["value"] + gets_ops, rel=1e-4)

    # Sub-millisecond average latency, lower-is-better, in ms.
    sets_lat = _metric(by["sets"], "latency_mean")
    assert sets_lat["unit"] == "ms"
    assert sets_lat["direction"] == "lower_is_better"
    assert 0.0 < sets_lat["value"] < 1.0
    assert sets_lat["value"] == pytest.approx(0.46076)

    # Percentile latency columns are read by header name (p50 / p99 / p99.9).
    assert _metric(by["sets"], "latency_p50")["value"] == pytest.approx(0.39100)
    assert _metric(by["sets"], "latency_p99")["value"] == pytest.approx(1.77500)
    assert _metric(by["sets"], "latency_p999")["value"] == pytest.approx(3.18300)

    # Bandwidth column.
    kb = _metric(by["sets"], "kb_per_sec")
    assert kb["unit"] == "kB/s"
    assert kb["direction"] == "higher_is_better"
    assert kb["value"] == pytest.approx(2937.46)

    # Hits/Misses present on Gets (Sets has "---" placeholders -> skipped).
    assert _metric(by["gets"], "misses_per_sec")["value"] == pytest.approx(27105.18)
    assert _metric(by["gets"], "misses_per_sec")["direction"] == "lower_is_better"
    with pytest.raises(AssertionError):
        _metric(by["sets"], "misses_per_sec")   # was "---", not emitted


def test_waits_row_all_placeholders():
    # The Waits row is all "---" except Ops/sec 0.00: only ops_per_sec emitted.
    rows = memtier_text.parse((FIXTURES / "output-text.txt").read_text())
    waits = _by_name(rows)["waits"]
    assert _metric(waits, "ops_per_sec")["value"] == pytest.approx(0.0)
    names = {m["name"] for m in waits["metrics"]}
    assert "latency_mean" not in names      # was "---"


# ---------------------------------------------------------------------------
# Format handling: sniff, timestamp prefix, histogram-header confusion.
# ---------------------------------------------------------------------------

def test_sniff_identifies_text():
    content = (FIXTURES / "output-text.txt").read_text()
    result = sniff(content)
    if result == "memtier/text":
        return  # the proposed _TEXT_PATTERNS entry has been merged centrally
    # Not yet merged: prove the PROPOSED sniff signature matches this fixture
    # (and only this fixture's stats header), so the central merge is safe.
    assert result is None, f"sniff mis-identified memtier text as {result!r}"
    # The proposed _TEXT_PATTERNS entry — searched against the RAW sample
    # (sniff's text tier does not pre-strip GH-log timestamps, so the
    # optional ISO-8601 prefix is embedded in the regex, as for linetimer).
    proposed = re.compile(
        r"^\s*(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+)?"
        r"Type\s+Ops/sec\s+Hits/sec\s+Misses/sec\b",
        re.MULTILINE,
    )
    assert proposed.search(content), "proposed memtier/text signature must match"
    # And it must NOT match the latency-distribution histogram header.
    assert not proposed.search(
        "2026-04-13T00:00:00.0Z Type     <= msec         Percent\n"
    )


def test_does_not_match_latency_histogram_header():
    # The "Type  <= msec  Percent" histogram header lacks Ops/sec and must
    # not be parsed as the stats table.
    only_histogram = (
        "Request Latency Distribution\n"
        "Type     <= msec         Percent\n"
        "------------------------------------------\n"
        "SET       0.039        0.000\n"
        "SET       0.151        5.000\n"
    )
    assert memtier_text.parse(only_histogram) == []


def test_tolerates_clean_artifact_table():
    # The artifact output.txt (no GH timestamps) parses identically.
    clean = (
        "ALL STATS\n"
        "=========================================\n"
        "Type         Ops/sec   Avg. Latency       KB/sec \n"
        "-----------------------------------------\n"
        "Sets        100.50         0.25000      512.00 \n"
        "Totals      100.50         0.25000      512.00 \n"
        "\n"
    )
    by = _by_name(memtier_text.parse(clean))
    assert set(by) == {"sets", "totals"}
    assert _metric(by["sets"], "ops_per_sec")["value"] == pytest.approx(100.50)
    assert _metric(by["sets"], "latency_mean")["value"] == pytest.approx(0.25)
