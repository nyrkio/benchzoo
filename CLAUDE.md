# CLAUDE.md

Guidance for working in **benchzoo**. Read this and the linked `docs/` before
adding or changing a parser or framework — the conventions below are
load-bearing and easy to get wrong by guessing.

## What benchzoo is

A Python library + corpus that ingests output from benchmark frameworks,
load-testing tools, unit-test runners, and CLI timing tools and converts it
into one uniform JSON shape (the Nyrkiö result schema). See
[`docs/design.md`](docs/design.md). Two halves:

- **The library** — parsers under `src/benchzoo/parsers/`, plus `sniff()`
  (content-based framework detection) and `find_parser()`. Published as
  `benchzoo` on PyPI.
- **The zoo** — `frameworks/<category>/<framework>/`: the *same* canonical
  sample benchmark implemented in each framework's idiom, run by that
  framework's CI workflow, with captured fixtures the parsers are tested
  against.

## The canonical sample benchmark — READ THIS FIRST

**[`docs/sample-benchmark.md`](docs/sample-benchmark.md) is the spec.** Every
framework implements the **same four benchmarks**, identical across the whole
zoo so results are comparable apples-to-apples:

- **benchmark1** — sleep-dominated, ~2.15 s wall time.
- **benchmark2** — tight `0..1000` CPU loop, sub-millisecond (use the
  language's "don't optimize away" primitive in compiled langs — `black_box`,
  `Blackhole`, etc.).
- **benchmark3** — write exactly 1.4 MB (decimal, 1,400,000 bytes) to
  `/dev/null` / a sink.
- **benchmark4** — change-detection showcase: sleep
  `2.15 + ((UTC_month mod 3) - 1)`, cycling `{1.15, 2.15, 3.15} s` with one
  step change per month boundary. Read the month as **UTC**.

Because the suite is fully specified, you know the expected numbers *before*
parsing (benchmark1 ≈ 2.15 s, etc.). That is what makes parsers cheap to write
("grep the output for 2.15") and verifiable.

Do **not** invent your own benchmarks for a new framework. Implement these four.

## Adding a framework + parser — the full contract

For each framework in [`docs/parser-targets.md`](docs/parser-targets.md), ship
ALL of:

1. **`frameworks/<category>/<framework>/`** — the four canonical benchmarks in
   the framework's idiom, plus a `run.sh` that produces the native output and
   writes it to `output.txt` (or `output.<ext>`). Generated `output.*` files
   are **gitignored** (`frameworks/**/output.*`); never commit them.
2. **`.github/workflows/<framework>.yml`** — sets up the runtime, runs the
   sample benchmark on push/PR touching the dir + `workflow_dispatch` + a
   **weekly `schedule:` cron** (the schedule is what makes benchmark4's
   change-detection signal meaningful over time — see
   [`docs/workflow-conventions.md`](docs/workflow-conventions.md)), and uploads
   the output as an artifact named `<framework>-output`. Give each workflow a
   distinct cron slot.
3. **`src/benchzoo/parsers/<framework>.py`** — a pure `parse(content: bytes|str)
   -> list[dict]`. One dict per test, shape:
   ```python
   {"test": {"test_name": "benchmark1"},
    "run":  {"passed": True},
    "env":  {"framework": {"name": "<framework>"}},
    "metrics": [{"name": "time", "unit": "s", "value": 2.15,
                 "direction": "lower_is_better"}]}
   ```
4. **Registry entry** in `src/benchzoo/parsers/__init__.py` (`PARSERS`), keyed
   `framework -> {format: module_name}`.
5. **A `sniff` signature** in `src/benchzoo/sniff.py` if the format is
   distinguishable (JSON/XML/CSV/text tiers). `sniff()` returns
   `"framework/format"`. If the output is captured from a GitHub Actions *log*
   (not an artifact), every line carries an ISO-8601 timestamp prefix —
   tolerate it (see `linetimer`/`criterion_text`).
6. **A real captured fixture** in `tests/data/<framework>-output/` (run the
   example, commit its native output — not a hand-written approximation).
7. **A test** in `tests/parsers/test_<framework>.py` with **ground-truth
   assertions** (`assert 2.0 < benchmark1_value < 2.3`), the load-bearing check
   that the parser reads the *right field*. benchmark4 uses a loose check
   (value ∈ `{1.15, 2.15, 3.15}` ± tolerance).
8. **A `_FIXTURE_EXPECTATIONS` entry** in `tests/test_discovery.py` mapping the
   fixture dir to its expected sniff framework (or `None` with a comment when
   the format is genuinely ambiguous, e.g. bencher text == cargo-bench text).

## Testing

- `pytest` (the repo default injects `-n auto` via `addopts`; to run a subset
  without xdist installed, pass `-o addopts=""`).
- `tests/test_discovery.py` checks every registry entry imports, sniffs every
  fixture (never a *wrong* framework), and that every parser is declared in
  `_FIXTURE_EXPECTATIONS`.
- Ground-truth assertions in the per-parser tests are mandatory; golden-file
  comparison alone can pass on structurally-identical garbage.

## Don't

- Don't invent benchmarks — implement the canonical four.
- Don't verify behavior with throwaway `python -c` scripts — add a test and run
  it; the test is the verification.
- Don't commit generated `frameworks/**/output.*` (gitignored).
