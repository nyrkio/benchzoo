# benchzoo design

## What this is

A Python library that detects performance changes — regressions and
improvements — in software projects by ingesting timing data from existing CI
runs, parsing it into a uniform shape, and (eventually) running change-point
detection on the resulting time series.

It is being built as a from-scratch Python rewrite of an earlier TypeScript
GitHub Action at [`nyrkio/change-detection`][fork], which was itself a fork of
[`benchmark-action/github-action-benchmark`][upstream]. The fork is
**reference-only**: benchzoo does not import from it, link to it at runtime,
or share code with it. It exists in this project's history as a source of
design ideas, parser fixtures, and test cases — nothing more.

[fork]: https://github.com/nyrkio/change-detection
[upstream]: https://github.com/benchmark-action/github-action-benchmark

## What it is not

- **Not a GitHub Action.** benchzoo does not run inside anyone's CI as a
  pipeline step. There is no `action.yml`, no `with:` inputs, no Node runtime.
- **Not a service.** benchzoo is a library, intended to be embedded in a
  larger Flask/FastAPI service that lives in a different repository. The web
  layer, persistence, and webhook handling all live in the parent project.
- **Not a client of any existing Nyrkiö backend.** A future Nyrkiö backend may
  exist; for now, benchzoo leaves a clean seam where uploads or detection
  requests would eventually plug in, but does not call out anywhere.
- **Not a change-detection algorithm (yet).** Change-point detection is part
  of the eventual product, but benchzoo does not implement it today. When
  it is added, it will use [Apache Otava][otava] (the donated DataStax
  "hunter" project, an E-divisive change-point detection tool for performance
  time series) — benchzoo will not roll its own algorithm.

[otava]: https://otava.apache.org/

## Eventual deployment

When the larger product around benchzoo is built, it will be installed into
target repositories as a **GitHub App**. The App will use its installation
token to:

1. Enumerate workflow runs on the target repo via the GitHub REST API.
2. Download logs and artifacts from those runs.
3. Parse timing data out of them using the parser layer in this library.
4. Feed parsed measurements into change detection.
5. Optionally report findings back to the target repo (PR comments, commit
   status, issues).

This is fundamentally a "look at CI from outside" model: a repo can be
onboarded with a single *Install* click, with no edits to its workflows.

**GitHub-first.** The first (and for now, only) supported CI platform is
GitHub Actions. Support for other platforms — GitLab CI, Buildkite,
CircleCI, Jenkins, etc. — is explicit future work, not on the v0 roadmap.
Crucially, this is an *ingest-layer* constraint, not a *parser-layer* one:
parsers never know or care where their input came from, so adding a new
CI platform later is purely a matter of writing a new ingest adapter
alongside the GitHub one. The parser corpus and the data model are
unaffected.

## Self-testing corpus / dogfood

Every framework that benchzoo supports gets implemented inside this
repository as a sample benchmark, plus a corresponding GitHub Actions
workflow that runs it on every push and PR and uploads the captured
native output as a workflow artifact. See
[`workflow-conventions.md`](workflow-conventions.md) for the convention.

This means benchzoo's own repository becomes a working example of
"many CI workflows emitting many flavors of benchmark output" — exactly
the kind of corpus the eventual GitHub-App ingest layer is designed to
consume. Once the ingest layer exists, the regression test for the
entire pipeline (parser → ingest → change detection) can simply point at
benchzoo itself. We dogfood our own product on its own repository.

It also means parser fixtures are not hand-curated one-off files: they
are produced by real CI runs against real framework versions, so any
upstream output-format change is caught the next time the workflow runs,
not the next time a human happens to notice.

Locally, the **same workflow YAML files** run under
[`nektos/act`][act] inside Docker containers that approximate GitHub's
hosted runners. That gives us a tight parser-development loop — edit
workflow, run locally, copy the captured output into a fixture,
iterate on the Python parser — without round-tripping through a push
and waiting on CI. The YAML is the single source of truth for both
local and remote runs; we don't maintain separate local/CI variants.
See [`workflow-conventions.md`](workflow-conventions.md#running-workflows-locally-with-act)
for the act usage conventions.

[act]: https://github.com/nektos/act

A second consequence of running a *known, canonical* sample benchmark
across every framework is that **parser correctness becomes verifiable,
not just lint-able**. Because we know test 1 sleeps for exactly 2.15
seconds, any parser whose output disagrees with that ground truth is
demonstrably wrong — regardless of whether its golden-file comparison
passes. Parser tests are expected to include ground-truth assertions
keyed to the known values in
[`sample-benchmark.md`](sample-benchmark.md), not just structural
snapshot matching. This also makes the parsers significantly cheaper to
develop: given a captured output, the field holding test 1's wall time
is found by grepping for `2.15` rather than by reverse-engineering the
format from documentation.

## Holistic parser surface

The most distinctive design choice is that benchzoo aims to consume a wide
range of input formats, not just a fixed list of benchmark frameworks. Anything
that emits per-test or per-operation timing is in scope:

- **Dedicated benchmark frameworks:** cargo bench / criterion, Google
  Benchmark, JMH, BenchmarkDotNet, pytest-benchmark, Catch2, benchmark.js,
  benchmarkluau, Julia BenchmarkTools, `go test -bench`, etc.
- **Unit test runners that report per-test duration:** `pytest --durations`,
  `jest --json`, `go test -json`, `vitest --reporter=json`, junitxml output
  from anything that emits it.
- **Plain CSV/JSON shapes** for tools that don't fit any of the above.

Parser implementations live in `src/benchzoo/parsers/`, one module per
format, all conforming to a common interface.

## Data model

Parsers convert framework-native output into the **Nyrkiö JSON** shape —
the format originally designed for the Nyrkiö backend's wire protocol —
adopted here as our common internal representation so that nothing needs
translation later if and when a Nyrkiö upload path is added.

**We use plain `dict` and `list` throughout — no dataclasses, no
TypedDict, no Pydantic.** The Nyrkiö format is JSON; we keep the Python
representation isomorphic to the JSON so parsers build results
incrementally with `{}` and `[]`, tests compare with `==`, and
serialization for upload is one `json.dumps()` call with no translation
layer. The cost — no static type checking on field names — is accepted
in exchange for the simplicity.

### The shape

A single Nyrkiö JSON document represents **one test run**. The
following is a real sample from nyrkio.com (with one benchzoo
extension: the `passed` key at the end):

```json
{
  "timestamp": 1706220908,
  "metrics": [
    {"name": "tps", "unit": "ops/s", "value": 3348, "direction": "higher_is_better"},
    {"name": "p90", "unit": "us",    "value": 125,  "direction": "lower_is_better"},
    {"name": "p99", "unit": "us",    "value": 280,  "direction": "lower_is_better"}
  ],
  "attributes": {
    "git_repo":   "https://github.com/nyrkio/nyrkio",
    "branch":     "main",
    "git_commit": "6995e2de6891c724bfeb2db33d7b87775f913ad1",
    "test_name":  "benchmark1"
  },
  "extra_info": {
    "client_threads": 8,
    "data_size": 256
  },
  "passed": true
}
```

**Note:** the sample above is the shape *after* the ingest layer has
filled in `timestamp` and the git-related attributes. A parser
producing this same result only sets `test_name` (inside `attributes`),
the `metrics`, and optionally `extra_info` and `passed`. It leaves
`timestamp` as `0` and omits the git-related attribute keys entirely.
See *Parser contract* below, and pay particular attention to the
semantics of `timestamp` — it is *not* the time at which the benchmark
ran.

### Field semantics

- **`timestamp`** — seconds since epoch, **git-derived, not benchmark
  run time.** Specifically: the committer timestamp of the git commit
  that produced this measurement — **preferably the merge commit**
  (the moment the code landed on the target branch), not the author
  commit timestamp. This anchors the measurement to a point in version
  history rather than to wall-clock time when CI happened to run, which
  is what change detection actually cares about: "at which commit did
  this metric shift?" is the question, and that's only answerable if
  the timestamp tracks commit history. **Parsers always set
  `timestamp: 0`**; the ingest layer assigns the real value when it
  looks up commit metadata. Many benchmark frameworks embed their own
  wall-clock "run time" in their output (pytest-benchmark's
  `machine_info.machine_time`, JMH's results date, hyperfine's
  start time, etc.) — **parsers must not use those values for
  `timestamp`**, because their semantics are wrong. If a parser wants
  to preserve a framework-reported wall clock for reference, it can
  stash it in `extra_info` (e.g. `extra_info["machine_time"]`).

- **`metrics`** — list of measurement dicts. Each has:
  - `name` — metric identifier (`"mean"`, `"min"`, `"max"`, `"stddev"`,
    `"p50"`, `"p90"`, `"p99"`, `"tps"`, …). Free-form string.
  - `unit` — unit string (`"s"`, `"ms"`, `"us"`, `"ns"`, `"ops/s"`,
    `"bytes"`, …).
  - `value` — the measurement as a number.
  - `direction` — optional; either `"higher_is_better"` or
    `"lower_is_better"`. Omit (don't set to `null`) when unknown.

  A single test run typically has multiple metrics (e.g.
  pytest-benchmark emits `mean`/`min`/`max`/`stddev`; a load test emits
  `tps`/`p50`/`p90`/`p99`/`error_rate`). All metrics from the same run
  live in the same dict.

- **`attributes`** — a tag bag of `{string: string}` carrying identity
  metadata about the test run. **Both the parser and the ingest layer
  write to this dict**:

  | Key          | Written by                    | Notes                                                                  |
  | ------------ | ----------------------------- | ---------------------------------------------------------------------- |
  | `test_name`  | **parser**                    | Canonical test identifier. Parsers **must** set this.                  |
  | `git_repo`   | ingest layer (when available) | **May be absent entirely** if not known. Parsers leave this out.       |
  | `branch`     | ingest layer (when available) | **May be absent entirely** if not known. Parsers leave this out.       |
  | `git_commit` | ingest layer (when available) | **May be absent entirely** if not known. Parsers leave this out.       |
  | (any other)  | either                        | Free-form. Values must be strings.                                     |

  **The parser identifies the test by writing `attributes["test_name"]`**,
  not by any separate `path` or top-level identifier. There is no
  wrapper dict at parse time — the TypeScript fork's
  `NyrkioJsonPath { path, results[] }` exists in the wire format for
  batching/grouping at upload time, but parsers do not produce it.

  **None of the git keys are guaranteed to be present.** The ingest
  layer sets them when it can (for example, when it's running inside
  CI with the commit it ran against in context). benchzoo is also
  usable on arbitrary JSON files that nobody has enriched with git
  metadata — in that case the git attributes simply aren't there and
  downstream consumers must cope with their absence. Don't write code
  that crashes on `d["attributes"]["git_commit"]` — always use `.get()`
  or a presence check.

- **`extra_info`** — optional free-form dict for benchmark-run
  parameters (`client_threads`, `data_size`, `hardware`, …). Typed
  values (numbers, booleans) are fine here. This is where
  parameterization lives if the source output carries it. Also the
  natural home for commit metadata like `head_commit`/`base_commit`
  when the ingest layer has it.

- **`passed`** — **benchzoo extension, not part of the Nyrkiö wire
  format.** Top-level boolean. Set to `false` when the parser sees a
  test that failed. Trivially strippable by a single `del d["passed"]`
  when serializing back to pure Nyrkiö JSON for upload. See
  *Library boundaries* below for the "record but don't filter" rule.

### Parser contract

A parser is a pure function:

```
parse(content: bytes | str) -> list[dict]
```

It returns a list of Nyrkiö JSON dicts — **one dict per test run** found
in the source output, each flat (no wrapper), each with:

- `attributes["test_name"]` set to a stable test identifier,
- `timestamp` set to `0` (always — see the field notes above; the
  ingest layer fills in the git commit timestamp later),
- the git-related attribute keys (`git_repo`, `branch`, `git_commit`)
  **left out entirely** (not set to empty strings — simply absent from
  the dict),
- `metrics` populated from the source,
- `extra_info` populated with any workload parameters the source
  carries, or omitted if none,
- `passed` set to `true` unless the source marks the test failed.

Concretely: for a pytest-benchmark output file that contains the four
tests of the canonical sample benchmark, `parse()` returns a list of
four dicts, each flat, each with a distinct `attributes["test_name"]`
(`"benchmark1"`, `"benchmark2"`, `"benchmark3"`, `"benchmark4"`), each
with `timestamp: 0`, and each with that test's metrics populated from
the source.

## Library boundaries

- **Pure parsers.** Each parser is a pure function: `bytes`/`str` in,
  `list[dict]` out (in the Nyrkiö JSON test-results shape defined above).
  No filesystem access, no network, no git context, no GitHub API.
  Git/CI metadata is injected at a higher layer if and when it's needed.
  (This is a deliberate departure from the fork, where parsers were
  entangled with the GitHub Actions runtime.)
- **No I/O coupling in the data model.** The data model *is* JSON —
  plain Python `dict`/`list`. Serialization to JSON is one `json.dumps()`
  away at the edge of the library; there are no dataclasses, TypedDicts,
  or Pydantic schemas to translate through.
- **Storage is out of scope.** benchzoo does not own a database or any
  on-disk format beyond the test fixtures it reads.
- **Failed runs are recorded, not filtered.** When a parser encounters a
  test or benchmark that failed (assertion failure, timeout, perf
  assertion, exception, etc.), it records the measurement and sets
  `d["passed"] = False` on the test-results dict. The library never
  automatically drops failed runs. Reasoning: a failure may itself be
  useful performance signal — a test newly hitting its timeout because
  it's now slower is exactly the kind of regression we want to catch —
  and even non-perf-related failures usually still produce a valid
  wall-clock measurement. Downstream consumers (the change-detection
  layer, dashboards, alerting) decide what to do with the flag. The
  library's job is to capture, not to judge. This rule applies uniformly
  to dedicated benchmark frameworks and to unit-test runners used as a
  timing source — both can mark results failed; both still flow through
  unfiltered. Because `passed` is a benchzoo extension rather than a
  Nyrkiö wire-format field, it sits at the top level of the wrapper
  dict, outside the `metrics` array, so it can be trivially stripped
  (`del d["passed"]`) when serializing back to pure Nyrkiö JSON.

## Decisions already made

| Decision                  | Choice                                       | Why                                                                       |
| ------------------------- | -------------------------------------------- | ------------------------------------------------------------------------- |
| Language                  | Python                                       | User preference; replacing TypeScript                                     |
| Package layout            | `src/benchzoo/`, `tests/` at repo root    | Standard Python `src/`-layout                                             |
| HTTP client (when needed) | `httpx`                                      | Streaming downloads for logs/artifacts; sync API today, async path open   |
| GitHub API wrapper        | None — call REST directly                    | Avoid PyGithub / githubkit design coupling; surface area is small         |
| CLI library (when needed) | `ConfigArgParse`                             | Unifies CLI flags, env vars, and YAML config behind one declaration       |
| Parser tests              | pytest, table-driven from fixture files      | Mirrors the fork's `normalCases` pattern; easy to extend per-fixture      |
| Change-point detection (when added) | Apache Otava                       | Don't roll our own; established E-divisive implementation                 |

`httpx`, `ConfigArgParse`, and the GitHub-API parts are deferred — see
[`PLAN.md`](../PLAN.md) for today's actual scope.
