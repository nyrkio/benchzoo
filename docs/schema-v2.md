# Result Schema v2 — draft

Status: **draft, uncommitted.** Two parsers (`pytest_benchmark_json`,
`hyperfine_json`) have been converted as a working demo; the other 40
still emit the v1 shape. See `docs/schema-v2.schema.json` for the
machine-readable JSON Schema.

## Motivation

The v1 shape is flat — one dict per test run with `timestamp`,
`attributes`, `metrics`, `passed`, `extra_info`. That served the "one
row per run, metrics as a repeated field" BigQuery shape well, but
three warts have accumulated:

1. `timestamp: 0` is a hack. Every parser sets it to zero; the ingest
   layer fills in the git-commit timestamp later. There's no place to
   record other times that exist in the raw output (build time, test
   wall-clock time).
2. Git / commit context is scattered: parsers sometimes see it
   (pytest-benchmark carries `commit_info`), sometimes not; consumers
   add it at ingest. Putting it in a named sub-document makes the
   source of truth explicit.
3. Environment (host CPU, OS) and system-under-test (app version,
   binary hash, config) get conflated in `attributes` / `extra_info`
   with no distinction. These are conceptually different: env is
   *where* the benchmark ran, SUT is *what* was measured.

## Shape

One test run = one dict, still. The top level is a fixed set of named
sub-documents plus `metrics` (list) and `passed` (bool).

```json
{
  "commit": {
    "repo": "nyrkio/benchzoo",
    "sha": "7d93d4c5975afa2d48c8a6712836c8748d5cf97b",
    "ref": "main",
    "commit_time": 1744455278
  },
  "run": {
    "run_id": "gh-actions-12345",
    "build_time": 1744455500,
    "test_time": 1744455620,
    "passed": true
  },
  "test": {
    "test_name": "benchmark1",
    "group": "sleep",
    "params": { "threads": 1, "data_size": 1400000 }
  },
  "sut": {
    "name": "my-app",
    "version": "1.2.3",
    "binary_sha": "abc..."
  },
  "env": {
    "os": "Linux",
    "arch": "x86_64",
    "cpu": "Intel(R) Xeon(R) Platinum 8370C CPU @ 2.80GHz",
    "cpu_count": 2,
    "runtime": "CPython 3.12.13",
    "framework": { "name": "pytest-benchmark", "version": "5.1.0" }
  },
  "metrics": [
    { "name": "mean",   "unit": "s", "value": 2.152, "direction": "lower_is_better" },
    { "name": "stddev", "unit": "s", "value": 0.004, "direction": "lower_is_better" },
    { "name": "ops",    "unit": "ops/s", "value": 0.464, "direction": "higher_is_better" }
  ]
}
```

## Field reference

### Top level

| Field | Type | Required? | Notes |
| --- | --- | --- | --- |
| `commit` | object | optional | VCS / source context. Populated by parsers when the framework carries it (pytest-benchmark, benchmarkdotnet); left empty when the ingest layer will fill it in. |
| `run` | object | optional | This specific execution. Distinct from `commit` — same commit can be run many times. |
| `test` | object | **`test_name` required** | What was measured, from the benchmark's point of view. |
| `sut` | object | optional | System under test — the thing being benchmarked. |
| `env` | object | optional | Environment that ran the benchmark. |
| `metrics` | array | **required, ≥1 entry** | The measurements. |
| `extra_info` | object | optional | Escape hatch for anything that doesn't fit in the named sub-documents. Free-form; most parsers will never populate it. Prefer a named sub-document when one applies. |

No scalar fields live at the top level — everything is either a
named sub-document (`commit`, `run`, `test`, `sut`, `env`,
`extra_info`) or the `metrics` array. A stray `timestamp: 0` at the
root would be the only scalar, and since it's always zero under the
v1 hack it doesn't deserve top-level status; commit-event time moved
into `commit.commit_time` and run-event time into `run.test_time`.

### `commit`

| Field | Type | Notes |
| --- | --- | --- |
| `repo` | string | Repo identifier. Conventionally `owner/name` or a URL. Parser-owned convention. |
| `sha` | string | Full commit SHA when available, short SHA otherwise. |
| `ref` | string | Human-facing identifier: branch, tag, or SHA. May duplicate `sha`. |
| `commit_time` | int (epoch seconds) | When the commit was created. Canonical timestamp for change-detection; the ingest layer may override if the parser couldn't determine it. |

### `run`

| Field | Type | Notes |
| --- | --- | --- |
| `run_id` | string | Opaque run identifier (GitHub Actions run ID, CI job ID, etc.). |
| `build_time` | int (epoch seconds) | When the SUT binary was built. |
| `test_time` | int (epoch seconds) | When the benchmark actually executed. Distinct from `commit_time` (commit may be hours/days older). |
| `passed` | bool | Pass/fail of this run. Absent means passed. A failed run can still carry metrics. |

### `test`

| Field | Type | Notes |
| --- | --- | --- |
| `test_name` | string | **Required.** Stable identifier for this test. The only truly mandatory field in the whole schema. |
| `group` | string | Suite grouping (pytest-benchmark `group`, JMH class, etc.). |
| `params` | object | Parameterization (threads, data size, input variant). Free-form; parsers stash what the framework reports. |

### `sut`

Free-form; common keys include `name`, `version`, `binary_sha`,
`config_hash`. Left empty when the framework doesn't know what's being
tested (e.g. unit-test-runner parsers — the "SUT" is the test code
itself and that's already captured by the commit SHA).

### `env`

| Field | Type | Notes |
| --- | --- | --- |
| `os` | string | e.g. `"Linux"`, `"Darwin"`, `"Windows"`. |
| `arch` | string | e.g. `"x86_64"`, `"aarch64"`. |
| `cpu` | string | CPU brand string (`cat /proc/cpuinfo` `model name`). |
| `cpu_count` | int | Logical core count. |
| `memory_gb` | number | Total system memory, gigabytes. |
| `runtime` | string | Interpreter / JVM / .NET version when relevant. |
| `framework` | object `{name, version}` | The benchmarking framework itself. |
| `runner` | string | e.g. `"github-actions"`, `"self-hosted"`, `"laptop"`. |

### `metrics`

List of measurement entries. Per-entry shape:

| Field | Type | Required? | Notes |
| --- | --- | --- | --- |
| `name` | string | **required** | Metric name. Conventional: `mean`, `stddev`, `median`, `min`, `max`, `p50`, `p95`, `p99`, `ops`, `duration`. |
| `value` | number | **required** | The number. |
| `unit` | string | optional but strongly encouraged | `s`, `ms`, `us`, `ns`, `ops/s`, `bytes/s`, etc. |
| `direction` | string | optional | `"lower_is_better"` or `"higher_is_better"`. |

Each stat from the framework becomes its own metric entry. A
pytest-benchmark run yielding `{min, max, mean, stddev, median, ops}`
emits six metric entries, not one entry with six fields.

## Validation

A document is valid iff:

- `test.test_name` is present and non-empty.
- `metrics` is a non-empty array.
- Each metric has `name` and `value`.
- Top-level keys are limited to `commit`, `run`, `test`, `sut`,
  `env`, `metrics`, `passed`, `extra_info`. Unknown top-level keys
  are rejected — `extra_info` is the escape hatch.
- Within each sub-document, unknown keys **are allowed** — parsers
  may stash framework-specific extras alongside the named ones.

See `schema-v2.schema.json`.

## Migration

- v1 `timestamp` → `commit.commit_time` (same semantics: epoch seconds
  of the commit).
- v1 `attributes.test_name` → `test.test_name`.
- v1 `attributes.{git_repo, branch, git_commit}` → `commit.{repo, ref, sha}`.
- v1 `extra_info` → preferably split across `test.params`, `sut`, or
  `env` based on meaning. When it genuinely doesn't fit any named
  sub-document, keep it in top-level `extra_info` (still permitted).
- v1 `metrics` → unchanged shape, same field semantics.
- v1 `passed` → `run.passed`.

## Open questions

- **Should `commit_time` live inside `commit` or at top level?** Kept
  it in `commit` for locality; the alternative is a top-level `time`
  sub-document with all three time fields.
- **Should `test_name` be promoted to top-level** for query
  ergonomics? Leaning no — nesting is one extra hop, and having a
  clean `test` block with `test_name, group, params` reads well.
- **Framework name in `env.framework` vs its own top-level key?**
  `env.framework` collapses it with OS/CPU; a top-level `framework`
  key would separate "what I ran under" from "what I ran on." Not
  sure yet.
