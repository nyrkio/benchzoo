# PLAN.md — archived

This file was the iterative working plan while benchzoo bootstrapped.
It served its purpose and is preserved here as history rather than as
active documentation.

**Current entry points:**

- Overall state and shipped frameworks: [`README.md`](README.md)
- Architecture and parser contract: [`docs/design.md`](docs/design.md)
- Catalog of supported and deferred formats:
  [`docs/parser-targets.md`](docs/parser-targets.md)
- Canonical sample benchmark: [`docs/sample-benchmark.md`](docs/sample-benchmark.md)
- CI / workflow conventions and Definition of Done:
  [`docs/workflow-conventions.md`](docs/workflow-conventions.md)

## Historical plan (preserved)

The initial session goal — "build something in Python that can parse
the outputs of as many benchmark and unit-test frameworks as
practical, and in the best case log files with timestamps" — is done.
The four-task roadmap below is what we followed to get there.

### Tasks (all complete)

1. **Catalog parser targets.** An opinionated list of benchmark
   frameworks, load-testing tools, frontend tools, unit test runners,
   and CLI timing tools we'd support. Lives at
   [`docs/parser-targets.md`](docs/parser-targets.md).
2. **Define the canonical sample benchmark.** A fixed four-test suite
   every framework implements. Tests 1–3 exercise parser correctness
   against fixed ground-truth values; test 4 produces a deterministic
   monthly change-point signal for the eventual Apache Otava
   showcase. Lives at [`docs/sample-benchmark.md`](docs/sample-benchmark.md).
3. **Implement the sample benchmark in each framework.** Done across
   42 frameworks, captured as real CI artifacts.
4. **Build parsers.** Done. 50+ parser modules, 250+ passing
   ground-truth tests, all wired up against the real captured
   fixtures.

### Out of scope (remained out of scope)

These belong to downstream consumers or future sessions:

- Change-detection algorithms — downstream consumer's job. Apache
  Otava is the eventual choice for that consumer; see
  [`docs/design.md`](docs/design.md).
- GitHub API ingest, workflow-run enumeration, log/artifact
  download — also downstream consumer's job.
- A CLI wrapper (no `ConfigArgParse` dependency yet).
- Persistence, webhooks, anything web-server-shaped.

### Working agreements that held

- The fork at `nyrkio/change-detection` stayed **reference-only**. No
  code was imported.
- The `[fork]` tags in the catalog were hints for cribbing fixtures or
  design ideas, not instructions to port.
- Every framework met the Definition of Done in
  [`docs/workflow-conventions.md`](docs/workflow-conventions.md)
  before it shipped.
