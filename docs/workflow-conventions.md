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
- **Dogfood corpus.** benchzoo's own repository becomes the canonical
  example of "many CI workflows emitting many flavors of benchmark
  output." When the GitHub-API ingest layer is eventually built (see
  *Eventual deployment* in [`design.md`](design.md)), it can be pointed at
  benchzoo's own repo as the end-to-end regression test for the whole
  pipeline: parser, ingest, and (eventually) change detection.

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
- These artifact names are **stable contracts**. The eventual ingest layer
  will look them up by name when fetching from the GitHub API. Renaming an
  artifact is a breaking change for downstream consumers and should be
  avoided.

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

We use [`nektos/act`][act] to run the **exact same workflow YAML files**
locally, inside Docker containers that approximate GitHub's hosted
runners. This is how parser development actually happens in practice:

1. Edit the workflow (or the sample benchmark inside it).
2. Run the workflow locally via `act`, capturing the output artifact to
   a local directory.
3. Copy the artifact into
   `frameworks/<category>/<framework>/fixtures/` (or wherever the
   fixture should live) as the reference input for parser development.
4. Write or iterate on the Python parser against that local fixture.
5. When the parser is green, commit and push. Real GitHub runners
   execute the same workflow as final verification.

The alternative — push every iteration, wait for CI, download the
artifact, repeat — is substantially slower and noisier.

The YAML file is the single source of truth for both act (local) and
GitHub (remote). We do not maintain parallel "local" and "CI" variants.

[act]: https://github.com/nektos/act

### Install

On Kubuntu / Debian-family Linux:

```bash
curl -sSL https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
```

On macOS: `brew install act`.

### Image selection

`act`'s default Docker image is intentionally minimal (no `sudo`, no
Python, no Node, etc.) — most benchzoo workflows will fail on it.
Pick a bigger image either per-invocation:

```bash
act -P ubuntu-latest=catthehacker/ubuntu:full-latest ...
```

…or pin it in `~/.actrc` so every invocation picks it up:

```
-P ubuntu-latest=catthehacker/ubuntu:full-latest
```

The `full` image is ~40 GB but is the closest approximation to GitHub's
hosted `ubuntu-latest`. `catthehacker/ubuntu:act-latest` is smaller and
often enough for simpler workflows that only need common toolchains.

### Running a single workflow

```bash
act push -W .github/workflows/hyperfine.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Explanation:

- `act push` — simulate a `push` event (matching our default trigger).
- `-W .github/workflows/hyperfine.yml` — run only this one workflow,
  not every workflow in the repo.
- `--artifact-server-path /tmp/benchzoo-artifacts` — where
  `actions/upload-artifact` outputs go. Without this flag, artifacts
  live inside the ephemeral container and are tedious to retrieve.

After the run, the captured output lands at:

```
/tmp/benchzoo-artifacts/<run-id>/<artifact-name>/<file>
```

### Simulating a schedule trigger

For workflows that accumulate the change-detection showcase series (see
test 4 in [`sample-benchmark.md`](sample-benchmark.md#test-4--change-detection-showcase-monthly-change-point)),
simulate the cron trigger:

```bash
act schedule -W .github/workflows/<framework>.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

### What act can't do

- **macOS and Windows runners.** act only supports Linux containers.
  Workflows targeting `macos-latest` or `windows-latest` (for example,
  XCTest) must be tested on GitHub proper.
- **Exact image parity.** `catthehacker`'s images approximate
  `ubuntu-latest` but are not byte-identical. If a workflow passes
  under `act` and fails on GitHub (or vice versa), trust GitHub's
  runner and file a local-parity gap; don't fork the workflow.
- **Some GitHub-only integrations.** Anything requiring genuine GitHub
  API context (real installation tokens, real event payloads beyond
  `push`/`schedule`/`pull_request`) may behave differently. act
  provides a placeholder `GITHUB_TOKEN` that works for most cases but
  not all.

### Secrets

Most benchzoo workflows are read-only and need no secrets. If one
does, pass them via `--secret` or `--secret-file`:

```bash
act push -W .github/workflows/foo.yml --secret-file .secrets
```

Keep `.secrets` out of the repo (it should be in `.gitignore`).

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
