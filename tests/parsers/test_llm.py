"""Evaluation harness for the LLM-based fallback parsers.

This test file is *deliberately* different from every other parser
test file in benchzoo:

- The LLM parsers are non-deterministic and require external
  resources (Anthropic API or a running Ollama instance). They are
  **not** part of the default test run.
- Instead, these tests are skipped by default. Setting environment
  variables turns them on:
    - ``BENCHZOO_RUN_LLM_ANTHROPIC=1`` enables the Anthropic tests
      (also requires ``ANTHROPIC_API_KEY``).
    - ``BENCHZOO_RUN_LLM_LOCAL=1`` enables the local Ollama tests.
- When enabled, tests iterate over a **subset** of the existing
  fixture corpus (the ones that best match the few-shot examples
  baked into the prompt), parse each one with the LLM, and assert
  that benchmark1's canonical ~2.15 s signature is recovered. We do
  NOT assert exact per-field equality against the deterministic
  parsers — that would defeat the purpose of the non-deterministic
  backend.

The harness also doubles as documentation: reading through these
tests tells you which formats the LLM parser handles confidently
and which it struggles with.
"""

from __future__ import annotations

import os
import pathlib

import pytest


DATA = pathlib.Path(__file__).parent.parent / "data"


# Formats where the canonical sample-benchmark's 2.15 s wall time is
# present in plain enough text that even a small LLM should find it.
# Each tuple: (fixture-relative path, format_hint, expected metric
# name, tolerance range for benchmark1, expected test_name).
_LLM_EVAL_CASES = [
    ("hyperfine-output/output.json",
     "hyperfine JSON export", "mean", (2.0, 2.3), "benchmark1"),
    ("go-test-bench-output/output.txt",
     "go test -bench text output", "ns_per_op", (2.0e9, 2.3e9), "benchmark1"),
    ("time-output/output-builtin.txt",
     "bash builtin time output, four benchmarks separated by === markers",
     "real", (2.0, 2.3), "benchmark1"),
    ("pytest-benchmark-output/output.json",
     "pytest-benchmark JSON report", "mean", (2.0, 2.3), "benchmark1"),
    ("custom-json-output/output-smaller.json",
     "custom JSON (customSmallerIsBetter variant)", "value", (2.0, 2.3), "benchmark1"),
]


def _metric(test_dict: dict, name: str) -> dict | None:
    for m in test_dict.get("metrics", []):
        if m.get("name") == name:
            return m
    return None


def _find_benchmark1(results: list[dict], expected_name: str) -> dict | None:
    for d in results:
        if d.get("test", {}).get("test_name") == expected_name:
            return d
    return None


@pytest.fixture(scope="module")
def _anthropic_parser():
    if os.environ.get("BENCHZOO_RUN_LLM_ANTHROPIC") != "1":
        pytest.skip("BENCHZOO_RUN_LLM_ANTHROPIC not set")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")
    from benchzoo.parsers import llm_anthropic
    return llm_anthropic


@pytest.fixture(scope="module")
def _local_parser():
    if os.environ.get("BENCHZOO_RUN_LLM_LOCAL") != "1":
        pytest.skip("BENCHZOO_RUN_LLM_LOCAL not set")
    from benchzoo.parsers import llm_local
    return llm_local


@pytest.mark.parametrize(
    "fixture,hint,metric_name,lo_hi,test_name", _LLM_EVAL_CASES
)
def test_llm_anthropic_finds_benchmark1_wall_time(
    _anthropic_parser, fixture, hint, metric_name, lo_hi, test_name
):
    content = (DATA / fixture).read_text()
    results = _anthropic_parser.parse(content, format_hint=hint)
    assert isinstance(results, list)
    assert len(results) >= 1

    b1 = _find_benchmark1(results, test_name)
    assert b1 is not None, (
        f"LLM did not produce a test_name={test_name!r} entry for {fixture}; "
        f"got names {[d.get('test', {}).get('test_name') for d in results]}"
    )
    m = _metric(b1, metric_name)
    assert m is not None, (
        f"LLM result for {fixture} lacks metric {metric_name!r}; "
        f"got {[x.get('name') for x in b1.get('metrics', [])]}"
    )
    lo, hi = lo_hi
    assert lo <= m["value"] <= hi, (
        f"LLM result for {fixture}: metric {metric_name} = {m['value']} "
        f"outside expected range [{lo}, {hi}]"
    )


@pytest.mark.parametrize(
    "fixture,hint,metric_name,lo_hi,test_name", _LLM_EVAL_CASES
)
def test_llm_local_finds_benchmark1_wall_time(
    _local_parser, fixture, hint, metric_name, lo_hi, test_name
):
    content = (DATA / fixture).read_text()
    results = _local_parser.parse(content, format_hint=hint)
    assert isinstance(results, list)
    assert len(results) >= 1

    b1 = _find_benchmark1(results, test_name)
    assert b1 is not None
    m = _metric(b1, metric_name)
    assert m is not None
    lo, hi = lo_hi
    assert lo <= m["value"] <= hi
