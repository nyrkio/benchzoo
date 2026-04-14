"""Shared prompt-building for the LLM-based fallback parsers.

Both :mod:`benchzoo.parsers.llm_anthropic` and
:mod:`benchzoo.parsers.llm_local` share the same prompt: an
instruction describing the Nyrkiö JSON schema, a handful of
compact worked examples drawn from the real parser corpus, and
the input content to parse.

Keeping the prompt here means both backends emit identical
requests (modulo API shape) so evaluation and tuning applies
uniformly to both.
"""

from __future__ import annotations


SYSTEM_PROMPT = """You are a benchmark-output parser for the benchzoo library.

Your job is to convert arbitrary benchmark or unit-test output (text, CSV, JSON, XML, anything) into the Nyrkiö v2 JSON shape. Follow these rules STRICTLY:

1. Return ONLY a JSON array. No prose, no markdown code fences, no commentary.
2. The array contains one object per test run found in the input. Each object uses these sub-documents:
     - "test":   { "test_name": "<stable identifier>", "group"?: "...", "params"?: {...} }  — REQUIRED. "test_name" is mandatory and non-empty.
     - "run":    { "passed": true|false, "test_time"?: <epoch-int>, "run_id"?: "..." }      — REQUIRED.
     - "env":    { "framework": {"name": "<kebab-case>", "version"?: "..."},
                   "os"?, "arch"?, "cpu"?, "cpu_count"?, "memory_gb"?, "runtime"?, "runner"? } — env.framework.name is the framework's kebab-case registry key.
     - "commit"?: { "repo"?, "sha"?, "ref"?, "commit_time"?: <epoch-int> } — omit the key entirely if unknown.
     - "sut"?:   { "name"?, "version"?, "url"?, ... } — system under test when distinct from the framework.
     - "metrics": array of measurement objects. Each measurement has:
         "name" (e.g. "mean", "p99", "ops_per_sec"), "unit" (e.g. "s", "ms", "us", "ns", "ops/s", "bytes"), "value" (a number), "direction" ("lower_is_better" or "higher_is_better"; omit when unknown).
     - "extra_info"?: object with any leftover metadata that doesn't fit above. Omit if empty.
   Do NOT include a top-level "timestamp" field, a top-level "attributes" object, or a top-level "passed" field — those were the v1 shape and are no longer used.

3. Be conservative about units. If the source says "2.15s" emit {"unit": "s", "value": 2.15}; if it says "2150ms" emit {"unit": "ms", "value": 2150}. Do NOT silently rescale.

4. Latencies/durations are lower_is_better; throughput / ops-per-sec / hz / rps are higher_is_better; counts (cache misses, page faults) are lower_is_better.

5. When test names appear with framework-specific decoration (e.g. "test_foo" in pytest, "BenchmarkFoo" in Go), strip the decoration: "test_foo" -> "foo", "BenchmarkFoo" -> "foo".

6. If the input is completely unrecognizable or empty, return []. Do not fabricate measurements.
"""


FEWSHOT_EXAMPLES = [
    # hyperfine JSON → Nyrkiö v2
    {
        "input": """{
  "results": [
    {
      "command": "benchmark1",
      "mean": 2.1529678, "stddev": 0.00006, "median": 2.1529894,
      "user": 0.00119, "system": 0.00173, "min": 2.15283, "max": 2.15304,
      "exit_codes": [0,0,0]
    }
  ]
}""",
        "output": """[
  {
    "test": {"test_name": "benchmark1"},
    "run": {"passed": true},
    "env": {"framework": {"name": "hyperfine"}},
    "metrics": [
      {"name": "mean",   "unit": "s", "value": 2.1529678, "direction": "lower_is_better"},
      {"name": "stddev", "unit": "s", "value": 0.00006,   "direction": "lower_is_better"},
      {"name": "median", "unit": "s", "value": 2.1529894, "direction": "lower_is_better"},
      {"name": "min",    "unit": "s", "value": 2.15283,   "direction": "lower_is_better"},
      {"name": "max",    "unit": "s", "value": 2.15304,   "direction": "lower_is_better"}
    ]
  }
]""",
    },
    # go test -bench text → Nyrkiö v2
    {
        "input": """BenchmarkBenchmark1-4    1    2150163312 ns/op    0 B/op    0 allocs/op
BenchmarkBenchmark2-4    1         628 ns/op    0 B/op    0 allocs/op""",
        "output": """[
  {
    "test": {"test_name": "benchmark1"},
    "run": {"passed": true},
    "env": {"framework": {"name": "go-test-bench"}},
    "metrics": [
      {"name": "ns_per_op", "unit": "ns", "value": 2150163312, "direction": "lower_is_better"}
    ]
  },
  {
    "test": {"test_name": "benchmark2"},
    "run": {"passed": true},
    "env": {"framework": {"name": "go-test-bench"}},
    "metrics": [
      {"name": "ns_per_op", "unit": "ns", "value": 628, "direction": "lower_is_better"}
    ]
  }
]""",
    },
    # plain text load-test summary → Nyrkiö v2
    {
        "input": """Requests per second:  12543.21 [#/sec]
Time per request:     7.97 [ms] (mean)
50%  7
95%  15
99%  28""",
        "output": """[
  {
    "test": {"test_name": "homepage"},
    "run": {"passed": true},
    "env": {"framework": {"name": "ab"}},
    "metrics": [
      {"name": "requests_per_sec", "unit": "ops/s", "value": 12543.21, "direction": "higher_is_better"},
      {"name": "latency_mean",     "unit": "ms",    "value": 7.97,     "direction": "lower_is_better"},
      {"name": "latency_p50",      "unit": "ms",    "value": 7,        "direction": "lower_is_better"},
      {"name": "latency_p95",      "unit": "ms",    "value": 15,       "direction": "lower_is_better"},
      {"name": "latency_p99",      "unit": "ms",    "value": 28,       "direction": "lower_is_better"}
    ]
  }
]""",
    },
]


def build_user_prompt(content: str, *, format_hint: str | None = None) -> str:
    """Assemble the user turn: few-shot examples + the real input."""
    parts: list[str] = []

    if format_hint:
        parts.append(f"Format hint: {format_hint}\n")

    parts.append("Here are three worked examples.\n")
    for i, ex in enumerate(FEWSHOT_EXAMPLES, start=1):
        parts.append(f"Example {i} input:\n{ex['input']}\n")
        parts.append(f"Example {i} output:\n{ex['output']}\n")

    parts.append(
        "Now parse this input and return ONLY the JSON array.\n\n"
        f"Input:\n{content}\n"
    )
    return "\n".join(parts)
