# Today's plan

This file is the working plan for the current iteration of perf-checks. It is
expected to change. For the long-term, evergreen design, see
[`docs/design.md`](docs/design.md).

## Goal for this session

**Build something in Python that can parse the outputs of as many benchmark
and unit-test frameworks as practical** — and, in the best case, log files
with timestamps. The session is iterative and the user is driving step by
step.

## Tasks

1. **Catalog parser targets.** Produce an opinionated list of the benchmark
   frameworks, load-testing tools, frontend tools, unit test runners, and
   CLI timing tools we want to support. Lives at
   [`docs/parser-targets.md`](docs/parser-targets.md).
2. **Define the canonical sample benchmark.** A small, fixed four-test
   suite that we will implement in *every* framework on the list, so that
   all our parser fixtures come from the same workload and can be compared
   apples-to-apples. Tests 1–3 exercise parser correctness against
   fixed ground-truth values; test 4 produces a deterministic monthly
   change-point signal for the eventual Apache Otava showcase. Lives at
   [`docs/sample-benchmark.md`](docs/sample-benchmark.md).
3. **Implement the sample benchmark in each framework.** For each framework
   in the catalog, write the canonical suite in its idiom, run it, and
   capture native output as a fixture in `tests/data/<framework>/`. (Gated
   on user signal — this is the first step that produces files outside
   `docs/`.)
4. **Build parsers.** For each captured fixture, write a Python parser
   that turns the framework's native output into the Nyrkiö JSON shape
   (flat `list[dict]`; plain dict/list, no dataclasses — see *Data
   model* in [`docs/design.md`](docs/design.md)). Tests are
   table-driven and include ground-truth assertions keyed to the known
   sample-benchmark values.

## Explicitly out of scope today

- The GitHub API integration (auth, workflow run enumeration, log/artifact
  download). Designed and discussed; deferred to a future session.
- Any change-point detection algorithm (will be Apache Otava when added —
  see `docs/design.md`).
- Any Nyrkiö backend integration.
- The CLI. (No `ConfigArgParse` dependency yet.)
- Persistence, webhooks, or anything web-server-shaped.
- Reporting back to GitHub (PR comments, issues, commit status).

## Phase status

**Planning phase complete.** Tasks 1 and 2 (catalog and sample-benchmark
spec) are done; the design surface in `docs/` is settled. The next work
is implementation — standing up the Python skeleton and shipping the
first framework end-to-end (sample benchmark + workflow + parser +
tests + README).

## Working agreements

- The fork at `nyrkio/change-detection` is **reference-only**. Tools
  tagged `[fork]` in the catalog had a parser there; that's a hint for
  cribbing fixtures or design ideas, not an instruction to port code.
- See [`docs/workflow-conventions.md`](docs/workflow-conventions.md)
  for the Definition of Done that every framework must meet before it
  ships.
