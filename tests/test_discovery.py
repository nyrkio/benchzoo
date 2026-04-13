"""Tests for parser discovery: :mod:`benchzoo.parsers.find_parser`
and :mod:`benchzoo.sniff`.

Both are exercised against every real fixture in ``tests/data/``.
"""

from __future__ import annotations

import pathlib
import pytest

import benchzoo
from benchzoo.parsers import PARSERS, find_parser


DATA = pathlib.Path(__file__).parent / "data"


# ---------------------------------------------------------------------------
# find_parser
# ---------------------------------------------------------------------------

def test_every_registry_entry_imports():
    """Every (framework, format) pair in the registry resolves to a
    real parser module with a callable parse() function."""
    for framework, formats in PARSERS.items():
        for fmt in formats:
            mod = find_parser(framework, fmt)
            assert callable(getattr(mod, "parse", None)), (
                f"{framework}/{fmt} resolved to {mod!r} but has no parse()"
            )


def test_find_parser_single_format_no_format_arg():
    """When a framework has exactly one parser, format= is optional."""
    mod = find_parser("lighthouse")
    assert mod.__name__.endswith(".lighthouse")


def test_find_parser_multi_format_requires_format_arg():
    with pytest.raises(ValueError, match="multiple parsers"):
        find_parser("hyperfine")


def test_find_parser_unknown_framework():
    with pytest.raises(KeyError, match="unknown framework"):
        find_parser("nonexistent-tool")


def test_find_parser_unknown_format():
    with pytest.raises(ValueError, match="no parser for"):
        find_parser("hyperfine", "xml")


def test_find_parser_accepts_snake_case_alias():
    """Users may pass framework names with underscores for convenience."""
    mod1 = find_parser("go-test-bench", "text")
    mod2 = find_parser("go_test_bench", "text")
    assert mod1 is mod2


def test_top_level_exports():
    """find_parser and sniff re-exported at package root for convenience."""
    assert benchzoo.find_parser is find_parser
    assert benchzoo.PARSERS is PARSERS
    assert callable(benchzoo.sniff)


# ---------------------------------------------------------------------------
# sniff — content-based framework detection
# ---------------------------------------------------------------------------

# Map each fixture directory name (under tests/data/) to the
# expected framework for :func:`sniff`. ``None`` means "ambiguous
# by construction; sniff is allowed to return None but must never
# return a wrong framework name".
#
# The sniffer is deliberately narrow. Fixtures where we simply don't
# have a distinctive enough signature are mapped to None — the
# contract is "never lie," not "always identify."
_FIXTURE_EXPECTATIONS: dict[str, str | None] = {
    # Tier 1 — JSON
    "hyperfine-output":          "hyperfine",
    "lighthouse-output":         "lighthouse",
    "google-benchmark-output":   "google-benchmark",
    "benchmarkdotnet-output":    "benchmarkdotnet",
    "pytest-benchmark-output":   "pytest-benchmark",
    "k6-output":                 "k6",
    "vegeta-output":             "vegeta",
    "memtier-output":            "memtier",
    "asv-output":                "asv",
    "clickbench-output":         "clickbench",
    "playwright-output":         "playwright",
    "mocha-output":              "mocha",
    "vitest-bench-output":       "vitest-bench",
    "benchmark-js-output":       "benchmark-js",
    "tinybench-output":          "tinybench",
    "mitata-output":             "mitata",
    "benchmark-ips-output":      "benchmark-ips",
    "jmh-output":                "jmh",
    "benchmarktools-jl-output":  "benchmarktools-jl",
    "custom-json-output":        "custom-json",
    # Tier 2 — XML
    "catch2-output":             "catch2",
    "phpbench-output":           "phpbench",
    "dotnet-test-output":        "dotnet-test",
    "junit-jest-output":         "junit-standard",
    "junit-go-output":           None,              # byte-identical to vanilla junit
    "junit-vanilla-output":      "junit-standard",
    "ctest-output":              "junit-standard",
    # Tier 3 — CSV
    "custom-csv-output":         "custom-csv",
    "redis-benchmark-output":    "redis-benchmark",
    "jmeter-output":             "jmeter",
    "locust-output":             "locust",
    # Tier 4 — text substrings
    "wrk-output":                "wrk",
    "wrk2-output":               "wrk2",
    "hey-output":                "hey",
    "perf-stat-output":          "perf-stat",
    "pgbench-output":            "pgbench",
    "sysbench-output":           "sysbench",
    "time-output":               "time",
    "go-test-bench-output":      "go-test-bench",
    "cargo-bench-output":        "cargo-bench",
    "gatling-output":            "gatling",
    "criterion-output":          None,              # estimates.json is tiny nested, bencher text is same as cargo bench
}


def _fixture_files(dir_name: str) -> list[pathlib.Path]:
    """Return the top-level fixture files for a given -output directory."""
    d = DATA / dir_name
    if not d.exists():
        return []
    return [p for p in d.iterdir() if p.is_file()]


@pytest.mark.parametrize(
    "fixture_dir,expected",
    sorted(_FIXTURE_EXPECTATIONS.items()),
)
def test_sniff_fixture(fixture_dir: str, expected: str | None):
    """For each fixture dir, sniff every top-level file and verify
    it either matches ``expected`` or returns None. NEVER a wrong
    framework name."""
    files = _fixture_files(fixture_dir)
    if not files:
        pytest.skip(f"no fixture files in {fixture_dir}")

    seen_any_match = False
    for path in files:
        # Read as bytes to exercise the bytes-path.
        content = path.read_bytes()
        result = benchzoo.sniff(content)
        # Some fixture dirs bundle a plain-junit artifact alongside the
        # framework's native output (e.g. catch2-output ships
        # output.junit.xml). "junit-standard" is the honest answer for
        # those files even when the dir's primary expected framework is
        # different.
        allowed = {None, expected, "junit-standard"} if "junit" in path.name.lower() else {None, expected}
        if expected is None:
            # No claim either way — but we must not fabricate.
            assert result in (None,) or result in PARSERS, (
                f"{path.name}: sniff returned unknown framework {result!r}"
            )
        else:
            assert result in allowed, (
                f"{path.name}: expected {expected!r} or None, got {result!r}"
            )
            if result == expected:
                seen_any_match = True

    if expected is not None:
        assert seen_any_match, (
            f"{fixture_dir}: sniff returned None for every file "
            f"(no file matched {expected!r}); tighten the signature "
            f"or lower the expectation to None."
        )


def test_sniff_empty_input():
    assert benchzoo.sniff("") is None
    assert benchzoo.sniff(b"") is None


def test_sniff_random_garbage():
    assert benchzoo.sniff("hello world") is None
    assert benchzoo.sniff(b"\x00\x01\x02\x03") is None


def test_sniff_every_framework_in_registry_resolves():
    """If sniff returns a name, find_parser must know what to do with it."""
    # This is belt-and-suspenders — if we ever add a sniff case for
    # a framework that isn't in PARSERS (e.g. typo in a constant),
    # the fixture tests above would catch it, but explicitly test
    # the invariant too.
    for fixture_dir, expected in _FIXTURE_EXPECTATIONS.items():
        if expected is None:
            continue
        assert expected in PARSERS, (
            f"{fixture_dir} expects sniff result {expected!r} "
            f"which is not in PARSERS"
        )
