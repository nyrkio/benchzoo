# CI workflow conventions

For every framework cataloged in
[`parser-targets.md`](parser-targets.md), benchzoo ships **both**:

1. A `frameworks/<category>/<framework>/` directory containing the sample
   benchmark implementation in that framework's idiom (the canonical
   three-test suite from [`sample-benchmark.md`](sample-benchmark.md)) plus
   any helper scripts and captured reference outputs.
2. A `.github/workflows/<framework>.yml` GitHub Actions workflow that sets
   up the framework's runtime, runs the sample benchmark on every push or
   PR that touches the framework's directory, and uploads the resulting
   native output as a workflow artifact.

These workflows serve a dual purpose:

- **Reproducibility.** The captured fixtures used by the parser tests are
  not hand-curated one-off files — they are produced by an actual CI run.
  Any change in framework version, output format, or platform behavior is
  caught the next time the workflow runs.
- **Test corpus for downstream consumers.** benchzoo's own repository
  is a working example of "many CI workflows emitting many flavors of
  benchmark output" — exactly the corpus that any downstream
  change-detection or analytics tool wants as its end-to-end test
  fixture.

## Naming convention

- **Filename:** `.github/workflows/<framework>.yml`
- **Casing:** lowercase, hyphens between words. Match the directory name
  under `frameworks/<category>/<framework>/`.
- **No category prefix.** The flat namespace under `.github/workflows/`
  matches GitHub's UI conventions and is easier to search than
  category-prefixed names.

Examples:

| Framework directory                              | Workflow file                                |
| ------------------------------------------------ | -------------------------------------------- |
| `frameworks/language/pytest-benchmark/`          | `.github/workflows/pytest-benchmark.yml`     |
| `frameworks/language/criterion/`                 | `.github/workflows/criterion.yml`            |
| `frameworks/database/sysbench/`                  | `.github/workflows/sysbench.yml`             |
| `frameworks/database/pgbench/`                   | `.github/workflows/pgbench.yml`              |
| `frameworks/unit-or-qa/pytest/`                  | `.github/workflows/pytest.yml`               |
| `frameworks/unit-or-qa/junit-jest/`              | `.github/workflows/junit-jest.yml`           |
| `frameworks/generic/hyperfine/`                  | `.github/workflows/hyperfine.yml`            |
| `frameworks/generic/time/`                       | `.github/workflows/time.yml`                 |

## Required workflow shape

Every workflow follows this skeleton. The deviations are framework-specific
(setup action, install command, run command, output filename).

```yaml
name: <framework>

on:
  push:
    branches: [main]
    paths:
      - 'frameworks/<category>/<framework>/**'
      - '.github/workflows/<framework>.yml'
  pull_request:
    paths:
      - 'frameworks/<category>/<framework>/**'
      - '.github/workflows/<framework>.yml'
  workflow_dispatch:

permissions:
  contents: read

jobs:
  benchmark:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frameworks/<category>/<framework>
    steps:
      - uses: actions/checkout@v4

      - name: Set up <runtime>
        uses: actions/setup-<runtime>@v4
        with:
          # runtime-specific options

      - name: Install <framework>
        run: <install command>

      - name: Run sample benchmark
        run: <run command — must write output to ./output.<ext>>

      - name: Upload output as artifact
        uses: actions/upload-artifact@v4
        with:
          name: <framework>-output
          path: frameworks/<category>/<framework>/output.<ext>
          if-no-files-found: error
```

## Path filters

Workflows trigger only when files under their own framework directory or
the workflow file itself change. We don't re-run all ~100 workflows on
every commit — most pushes will touch zero or one workflow.

## Artifact naming

- Each workflow uploads **exactly one** artifact named `<framework>-output`.
- The artifact contains the captured native output of the framework's
  sample benchmark run.
- These artifact names are **stable contracts** for downstream
  consumers (anything fetching from this repo by artifact name).
  Renaming an artifact is a breaking change and should be avoided.

## Multi-format capture

Many frameworks support multiple output formats (JSON, CSV, text, XML,
etc.). **Workflows capture all common machine-readable formats**, not
just the richest one. The rationale: benchzoo's target use case is "the
user already ran their benchmarks in whatever format they chose, and we
parse that." Each output format gets a separate parser module.

Concretely, the `run.sh` script for such a framework invokes the
benchmark multiple times (once per output format) or uses
framework-specific flags to emit multiple outputs in a single run.
All output files land in the single `<framework>-output` artifact:

```yaml
- name: Upload output as artifact
  uses: actions/upload-artifact@v4
  with:
    name: <framework>-output
    path: |
      frameworks/<category>/<framework>/output.json
      frameworks/<category>/<framework>/output.csv
      frameworks/<category>/<framework>/output.txt
    if-no-files-found: error
```

"All common" means: formats that are machine-readable and that real
users actually use. HTML reports, binary caches, and niche internal
formats can be skipped. When in doubt, include — a fixture we don't
need is cheaper than a format gap.

For frameworks where capturing multiple formats requires running the
benchmark more than once, accept the extra CI time. The runs are
typically fast (the canonical sample-benchmark takes seconds) and CI
minutes are cheap relative to the value of having real fixtures for
every parser. If a specific framework is so slow that running it 3×
is problematic, document it in the framework's README and pick the
two most common formats.

## Service containers (for database / network benchmarks)

Some frameworks need a service to benchmark against — sysbench needs
MySQL, pgbench needs Postgres, ClickBench needs ClickHouse, k6 needs an
HTTP target, etc. These workflows declare a service container:

```yaml
jobs:
  benchmark:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: postgres
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      ...
```

Pin the service image to a specific major version. Don't use `:latest`.

## When `ubuntu-latest` is not enough

Some frameworks need OS-specific runners (XCTest needs macOS,
Windows-only tools need Windows). Specify the appropriate `runs-on:` per
workflow.

**Avoid matrices** (`strategy.matrix`) unless the *output format* differs
across OSes. We only need one captured fixture per framework, not per
(framework, OS) tuple. Multi-OS matrices waste CI minutes and produce
fixtures that are hard to compare.

## Versioning the framework

Pin the framework version explicitly in the install step:

```yaml
- run: pip install pytest-benchmark==4.0.0
```

Not `pip install pytest-benchmark`. We want the captured fixture to be a
function of a known input. Whenever we deliberately bump the version, the
diff in the captured output is part of the PR — that's the entire point.

## Caching

Cache toolchain installations with the standard `actions/setup-*` cache
flags (`cache: pip`, `cache: maven`, `cache: cargo`, etc.) — this is
cheap and keeps CI fast as the workflow count grows. Don't cache the
captured output.

## Optional: scheduled runs for test 4 / change-detection showcase

[Test 4 in `sample-benchmark.md`](sample-benchmark.md#test-4--change-detection-showcase-monthly-change-point)
is designed to produce a reproducible time series with one change point
per month. For that series to actually accumulate, the workflow must
run more often than just on push/PR — otherwise a quiet week leaves a
hole in the history and, over long periods, there's no signal for
Apache Otava to find change points in.

Add a `schedule:` trigger for any workflow whose captured outputs are
meant to feed the change-detection showcase:

```yaml
on:
  push: ...
  pull_request: ...
  workflow_dispatch:
  schedule:
    - cron: '0 12 * * *'    # daily at 12:00 UTC
```

Daily is usually enough. Hourly is wasteful. Avoid `0 0 * * *` (midnight
UTC): the transition from month N to month N+1 happens right at that
moment and you get runs with ambiguous month values under skew.

## Concurrency

Each workflow declares a per-branch concurrency group so a force-push to
a feature branch doesn't run two benchmark jobs in parallel:

```yaml
concurrency:
  group: <framework>-${{ github.ref }}
  cancel-in-progress: true
```

## Running workflows locally with `act`

Moved to [`act.md`](act.md) — install notes, image selection,
schedule-trigger simulation, limitations, and secrets handling all
live there. The anchor on this heading stays stable so older links
continue to resolve.

## What "done" looks like for a framework

A framework is considered "shipped" when:

1. `frameworks/<category>/<framework>/` contains the sample-benchmark
   implementation in that framework's idiom.
2. `.github/workflows/<framework>.yml` exists, runs green, and uploads
   the output artifact.
3. The corresponding parser in `src/benchzoo/parsers/` (or wherever
   parsers eventually live) consumes that fixture and converts it into
   a `list[dict]` of flat Nyrkiö JSON documents (see *Data model* in
   [`design.md`](design.md)), one dict per test run with
   `attributes["test_name"]` set, with parametrized tests.
4. The fixture file is checked in alongside the parser tests so the
   tests are runnable without re-running CI.
5. **The parser tests include ground-truth assertions** keyed to the
   known values from
   [`sample-benchmark.md`](sample-benchmark.md#ground-truth-values-and-why-they-matter)
   — at minimum, that test 1's measured wall time falls within
   `2.0 < t < 2.3` seconds. Golden-file / snapshot tests are
   encouraged as a second layer but do not satisfy this requirement on
   their own.
6. **`frameworks/<category>/<framework>/README.md`** exists and
   cross-links the framework's other surfaces so a reader can hop
   between them in one click each:
   - The sample benchmark implementation in the same directory.
   - The workflow file at
     `.github/workflows/<framework>.yml`.
   - The workflow's live run history on GitHub at
     `https://github.com/nyrkio/benchzoo/actions/workflows/<framework>.yml`.
   - The parser source file.
   - The parser test file.

   See the README template below.

### README template

Each `frameworks/<category>/<framework>/README.md` follows this shape.
(Paths assume a framework at three levels of nesting below the repo
root; adjust `../../../` if the directory depth differs.)

```markdown
# <framework-name>

<one-sentence description of the framework and its language/ecosystem>

## Links

- **Sample benchmark** — see the files in this directory
  (e.g. [`benchmark.sh`](benchmark.sh))
- **Workflow** — [`.github/workflows/<framework>.yml`](../../../.github/workflows/<framework>.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/<framework>.yml>
- **Parser** — [`src/benchzoo/parsers/<framework>.py`](../../../src/benchzoo/parsers/<framework>.py)
- **Parser tests** — [`tests/parsers/test_<framework>.py`](../../../tests/parsers/test_<framework>.py)

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) in
<framework> idiom:

- **Test 1** (sleep 2.15 s) — …
- **Test 2** (tight CPU loop) — … *(if compiled, note how the empty
  loop is kept from being optimized away — e.g. `std::hint::black_box`
  in Rust, `Blackhole.consume` in JMH, etc.)*
- **Test 3** (write 1.4 MB to /dev/null) — …
- **Test 4** (monthly change point) — …

## Running locally

\```bash
act push -W .github/workflows/<framework>.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
\```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/<framework>-output/`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

## Parser notes

<anything framework-specific the parser needs to know about — output
format quirks, version compatibility, unit conventions, missing fields,
subtest handling, whether failures surface in the output, etc.>
```

The cross-links matter because they make the repo self-navigating. A
reader landing on a parser test from a grep result can hop to the
framework directory, see what the sample benchmark looks like in that
framework's idiom, click through to the workflow file, and from there
to the live CI history — all without having to know the directory
layout in advance. Every framework's README is written to the same
template so the navigation is predictable.
