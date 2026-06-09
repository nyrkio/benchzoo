"""Parsers that convert framework-native output into Nyrkiö JSON.

Each parser module in this package exposes a single pure function::

    def parse(content: bytes | str) -> list[dict]: ...

Returning a list of flat dicts in the Nyrkiö JSON shape — one dict per
test run found in ``content``. See ``docs/design.md`` for the full
contract.

The data model is plain ``dict`` / ``list`` throughout; there are no
dataclasses, TypedDicts, or Pydantic schemas. The Python representation
is isomorphic to the JSON wire format, so serialization at the edge of
the library is one ``json.dumps()`` call.

A minimal result from a parser looks like::

    [
        {
            "timestamp": 0,
            "metrics": [
                {"name": "mean", "unit": "s", "value": 2.15, "direction": "lower_is_better"},
            ],
            "attributes": {"test_name": "benchmark1"},
            "passed": True,
        },
        ...
    ]

Parsers **must**:

- set ``attributes["test_name"]`` to a stable identifier,
- set ``timestamp`` to ``0`` (the ingest layer fills in the real
  git-commit timestamp later — parsers never read the framework's
  wall-clock time for this field),
- leave the git-related attribute keys (``git_repo``, ``branch``,
  ``git_commit``) out of ``attributes`` entirely,
- populate ``metrics`` from the source output,
- record failed tests with ``passed: False`` rather than dropping them.


Parser discovery
----------------

The :data:`PARSERS` registry below is the library's phone book: it
maps a framework name (the kebab-case string that matches the
directory name under ``frameworks/``) to one or more
``(format, module_name)`` pairs.

Callers who already know which framework + format they're looking at
can skip the registry and ``from benchzoo.parsers import <module>``
directly — that's still the blessed, zero-indirection path. The
registry exists so downstream consumers (e.g. a GitHub App ingest
layer) don't have to hand-maintain the name→module map.

For content-based discovery (sniffing), see :mod:`benchzoo.sniff`.
"""

from __future__ import annotations

import importlib
from types import ModuleType


# Framework name (kebab-case, matches frameworks/<category>/<name>/)
#     →   { format name   →   parser module name under benchzoo.parsers }
#
# Format names are the short identifiers a user would say: "json",
# "csv", "xml", "text", plus a few format-variant words for frameworks
# that ship multiple text flavors ("bencher", "estimates", "trx",
# "builtin", "gnu", "summary", "ndjson", "junit", "bigger_is_better",
# "smaller_is_better").
#
# Where a framework has only one parser, we pick the one obvious key
# ("json" for JSON-emitters, "text" for text-emitters, "xml" for XML).
PARSERS: dict[str, dict[str, str]] = {
    # Dedicated benchmark libraries
    "criterion":         {"estimates": "criterion_estimates",
                          "bencher":   "criterion_bencher",
                          "text":      "criterion_text"},
    "cargo-bench":       {"text":      "cargo_bench_libtest"},
    "linetimer":         {"text":      "linetimer"},
    "google-benchmark":  {"json":      "google_benchmark_json",
                          "csv":       "google_benchmark_csv",
                          "text":      "google_benchmark_text"},
    "catch2":            {"xml":       "catch2_xml",
                          "junit":     "junit_standard"},
    "jmh":               {"json":      "jmh_json",
                          "csv":       "jmh_csv"},
    "benchmarkdotnet":   {"json":      "benchmarkdotnet_json",
                          "csv":       "benchmarkdotnet_csv"},
    "go-test-bench":     {"text":      "go_bench_text",
                          "json":      "go_bench_json"},
    "pytest-benchmark":  {"json":      "pytest_benchmark_json",
                          "junit":     "junit_pytest"},
    "asv":               {"json":      "asv"},
    "benchmark-js":      {"json":      "benchmark_js"},
    "tinybench":         {"json":      "tinybench"},
    "mitata":            {"json":      "mitata"},
    "vitest-bench":      {"json":      "vitest_bench"},
    "benchmarktools-jl": {"json":      "benchmarktools_jl"},
    "phpbench":          {"xml":       "phpbench_xml"},
    "benchmark-ips":     {"json":      "benchmark_ips"},
    # Load / HTTP testing
    "k6":                {"summary":   "k6_summary",
                          "ndjson":    "k6_ndjson"},
    "wrk":               {"text":      "wrk"},
    "wrk2":              {"text":      "wrk2"},
    "hey":               {"text":      "hey"},
    "vegeta":            {"json":      "vegeta_json"},
    "locust":            {"csv":       "locust_csv"},
    "jmeter":            {"csv":       "jmeter_csv"},
    "gatling":           {"log":       "gatling_log"},
    # Databases
    "pgbench":           {"text":      "pgbench"},
    "sysbench":          {"text":      "sysbench"},
    "redis-benchmark":   {"csv":       "redis_benchmark_csv"},
    "memtier":           {"json":      "memtier_json"},
    "clickbench":        {"json":      "clickbench"},
    # Frontend
    "lighthouse":        {"json":      "lighthouse"},
    # Unit-test runners used as timing source
    "mocha":             {"json":      "mocha_json"},
    "junit-jest":        {"xml":       "junit_standard"},
    "junit-go":          {"xml":       "junit_go"},
    "junit-vanilla":     {"xml":       "junit_standard"},
    "junit-standard":    {"xml":       "junit_standard"},
    "dotnet-test":       {"trx":       "dotnet_test_trx"},
    "ctest":             {"xml":       "junit_standard"},
    "playwright":        {"json":      "playwright_json"},
    # Generic / escape hatches
    "hyperfine":         {"json":      "hyperfine_json",
                          "csv":       "hyperfine_csv"},
    "time":              {"builtin":   "time_builtin",
                          "gnu":       "time_gnu"},
    "perf-stat":         {"text":      "perf_stat_text"},
    "custom-json":       {"bigger_is_better":  "custom_bigger_is_better",
                          "smaller_is_better": "custom_smaller_is_better"},
    "custom-csv":        {"csv":       "custom_csv"},
    # Historical Nyrkiö JSON (pre-benchzoo): carries git provenance +
    # commit timestamp inline in the data file; accepted as either a
    # JSON array or NDJSON.
    "nyrkio-json":       {"v1":        "nyrkio_json_v1"},
}


def find_parser(framework: str, format: str | None = None) -> ModuleType:
    """Import and return the parser module for ``framework`` (+ ``format``).

    ``framework`` is the kebab-case name (e.g. ``"hyperfine"``,
    ``"pytest-benchmark"``, ``"go-test-bench"``). Snake-case variants
    are accepted too for caller convenience.

    ``format`` is optional when a framework has only one parser. When
    multiple formats are registered, ``format`` is required — a
    ``ValueError`` names the available options.
    """
    canonical = framework.replace("_", "-")
    if canonical not in PARSERS:
        raise KeyError(
            f"unknown framework {framework!r}; known: "
            f"{', '.join(sorted(PARSERS))}"
        )

    formats = PARSERS[canonical]
    if format is None:
        if len(formats) == 1:
            (module_name,) = formats.values()
        else:
            raise ValueError(
                f"framework {framework!r} has multiple parsers "
                f"({sorted(formats)}); pass format="
            )
    else:
        if format not in formats:
            raise ValueError(
                f"no parser for framework={framework!r} "
                f"format={format!r}; available: {sorted(formats)}"
            )
        module_name = formats[format]

    return importlib.import_module(f"benchzoo.parsers.{module_name}")
