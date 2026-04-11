# perf-checks design

## What this is

A Python library that detects performance changes — regressions and
improvements — in software projects by ingesting timing data from existing CI
runs, parsing it into a uniform shape, and (eventually) running change-point
detection on the resulting time series.

It is being built as a from-scratch Python rewrite of an earlier TypeScript
GitHub Action at [`nyrkio/change-detection`][fork], which was itself a fork of
[`benchmark-action/github-action-benchmark`][upstream]. The fork is
**reference-only**: perf-checks does not import from it, link to it at runtime,
or share code with it. It exists in this project's history as a source of
design ideas, parser fixtures, and test cases — nothing more.

[fork]: https://github.com/nyrkio/change-detection
[upstream]: https://github.com/benchmark-action/github-action-benchmark

## What it is not

- **Not a GitHub Action.** perf-checks does not run inside anyone's CI as a
  pipeline step. There is no `action.yml`, no `with:` inputs, no Node runtime.
- **Not a service.** perf-checks is a library, intended to be embedded in a
  larger Flask/FastAPI service that lives in a different repository. The web
  layer, persistence, and webhook handling all live in the parent project.
- **Not a client of any existing Nyrkiö backend.** A future Nyrkiö backend may
  exist; for now, perf-checks leaves a clean seam where uploads or detection
  requests would eventually plug in, but does not call out anywhere.
- **Not a change-detection algorithm (yet).** Change-point detection is part
  of the eventual product, but perf-checks does not implement it today. When
  it is added, it will use [Apache Otava][otava] (the donated DataStax
  "hunter" project, an E-divisive change-point detection tool for performance
  time series) — perf-checks will not roll its own algorithm.

[otava]: https://otava.apache.org/

## Eventual deployment

When the larger product around perf-checks is built, it will be installed into
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

## Holistic parser surface

The most distinctive design choice is that perf-checks aims to consume a wide
range of input formats, not just a fixed list of benchmark frameworks. Anything
that emits per-test or per-operation timing is in scope:

- **Dedicated benchmark frameworks:** cargo bench / criterion, Google
  Benchmark, JMH, BenchmarkDotNet, pytest-benchmark, Catch2, benchmark.js,
  benchmarkluau, Julia BenchmarkTools, `go test -bench`, etc.
- **Unit test runners that report per-test duration:** `pytest --durations`,
  `jest --json`, `go test -json`, `vitest --reporter=json`, junitxml output
  from anything that emits it.
- **Plain CSV/JSON shapes** for tools that don't fit any of the above.

Parser implementations live in `src/perf_checks/parsers/`, one module per
format, all conforming to a common interface.

## Library boundaries

- **Pure parsers.** Each parser is a pure function: bytes/str in, list of
  `BenchmarkResult` out. No filesystem access, no network, no git context, no
  GitHub API. Git/CI metadata is injected at a higher layer if and when it's
  needed. (This is a deliberate departure from the fork, where parsers were
  entangled with the GitHub Actions runtime.)
- **No I/O coupling in the data model.** `BenchmarkResult` is a plain
  dataclass; serialization to JSON/YAML/etc. is a separate concern at the edge
  of the library.
- **Storage is out of scope.** perf-checks does not own a database or any
  on-disk format beyond the test fixtures it reads.
- **Failed runs are recorded, not filtered.** When a parser encounters a
  test or benchmark that failed (assertion failure, timeout, perf
  assertion, exception, etc.), it records the measurement with a
  `passed: false` flag and emits it like any other. The library never
  automatically drops failed runs from the result list. Reasoning: a
  failure may itself be useful performance signal — a test newly hitting
  its timeout because it's now slower is exactly the kind of regression
  we want to catch — and even non-perf-related failures usually still
  produce a valid wall-clock measurement. Downstream consumers (the
  change-detection layer, dashboards, alerting) decide what to do with the
  flag. The library's job is to capture, not to judge. (This rule applies
  uniformly to dedicated benchmark frameworks and to unit-test runners
  used as a timing source — both can mark results failed; both still
  flow through unfiltered.)

## Decisions already made

| Decision                  | Choice                                       | Why                                                                       |
| ------------------------- | -------------------------------------------- | ------------------------------------------------------------------------- |
| Language                  | Python                                       | User preference; replacing TypeScript                                     |
| Package layout            | `src/perf_checks/`, `tests/` at repo root    | Standard Python `src/`-layout                                             |
| HTTP client (when needed) | `httpx`                                      | Streaming downloads for logs/artifacts; sync API today, async path open   |
| GitHub API wrapper        | None — call REST directly                    | Avoid PyGithub / githubkit design coupling; surface area is small         |
| CLI library (when needed) | `ConfigArgParse`                             | Unifies CLI flags, env vars, and YAML config behind one declaration       |
| Parser tests              | pytest, table-driven from fixture files      | Mirrors the fork's `normalCases` pattern; easy to extend per-fixture      |
| Change-point detection (when added) | Apache Otava                       | Don't roll our own; established E-divisive implementation                 |

`httpx`, `ConfigArgParse`, and the GitHub-API parts are deferred — see
[`PLAN.md`](../PLAN.md) for today's actual scope.
