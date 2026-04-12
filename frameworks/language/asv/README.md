# asv (airspeed velocity)

[asv](https://asv.readthedocs.io/) is a history-aware Python
benchmarking framework developed for the NumPy / SciPy / scikit-learn
ecosystem. Unlike most per-run benchmark tools, asv is designed around
tracking performance across many commits: it stores results on disk
keyed by commit hash and can render an HTML dashboard of time series
out of the box. Benchmarks are defined as methods on classes in a
dedicated ``benchmarks/`` directory.

## Links

- **Sample benchmark** — see [`benchmarks/benchmarks.py`](benchmarks/benchmarks.py)
- **Workflow** — [`.github/workflows/asv.yml`](../../../.github/workflows/asv.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/asv.yml>
- **Parser** — [`src/benchzoo/parsers/asv.py`](../../../src/benchzoo/parsers/asv.py) *(not yet written — pending a real captured fixture)*
- **Parser tests** — [`tests/parsers/test_asv.py`](../../../tests/parsers/test_asv.py) *(not yet written)*

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) in asv
idiom. All four tests live as methods on a single ``SampleBenchmark``
class. asv discovers any method whose name starts with ``time_`` and
treats it as a timing benchmark; method name → test identifier is by
stripping the ``time_`` prefix (so ``time_benchmark1`` →
``"benchmark1"``).

- **Test 1** (sleep 2.15 s) — ``time.sleep(2.15)``.
- **Test 2** (tight CPU loop) — ``for _ in range(1000): pass``. Python
  is interpreted and does not eliminate empty loops, so no
  ``black_box`` trick is needed.
- **Test 3** (write 1.4 MB to /dev/null) — ``os.urandom(1_400_000)``
  written to ``/dev/null`` opened in ``"wb"`` mode.
- **Test 4** (monthly change point) — computes
  ``sleep_s = 2.15 + ((month % 3) - 1)`` where ``month`` is the current
  UTC month and sleeps for that many seconds.

### Output formats captured

asv emits a single raw JSON results file per (machine, commit, env)
tuple, stored under ``.asv/results/<machine>/<commit>-<env>.json``. The
``run.sh`` script locates that file and copies it to ``output.json`` at
the framework dir root for artifact upload. asv also generates a static
HTML dashboard under ``.asv/html/`` via ``asv publish``; that is not
machine-readable and is not captured.

### Tricky asv invocation flags

- ``asv machine --yes`` — asv refuses to run until it knows which
  machine it is running on; ``--yes`` accepts defaults
  non-interactively so the step works in headless CI.
- ``asv run --python=same`` — by default ``asv run`` provisions a fresh
  virtualenv per Python version in the matrix. We already pin Python
  at the CI layer and install asv into that interpreter via
  ``requirements.txt``, so ``--python=same`` tells asv to reuse the
  current environment.
- ``asv run --quick`` — caps samples per benchmark, which matters for
  the multi-second sleep tests (otherwise a single CI run could take
  minutes).
- ``asv run --show-stderr`` — surfaces benchmark errors in the CI log
  instead of hiding them inside asv's results.

## Running locally

```bash
act push -W .github/workflows/asv.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/asv-output/output.json`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with the requirements installed locally, you can skip
`act` entirely and run

```bash
pip install -r requirements.txt
./run.sh
```

from this directory.

## Parser notes

asv's results JSON is compact but dense. A representative shape is:

```json
{
  "version": 2,
  "commit_hash": "abc123...",
  "date": 1712880000000,
  "env_name": "virtualenv-py3.12",
  "python": "3.12",
  "params": { "machine": "...", "os": "...", "arch": "...", ... },
  "requirements": {},
  "result_columns": [
    "result", "params", "version", "started_at", "duration",
    "stats_ci_99_a", "stats_ci_99_b", "stats_q_25", "stats_q_75",
    "stats_number", "stats_repeat", "samples", "profile"
  ],
  "results": {
    "benchmarks.SampleBenchmark.time_benchmark1": [
      [2.1500xxx], [], "hashv1", 1712880000001, 5.0,
      [2.149], [2.151], [2.149], [2.151],
      [1], [5], null, null
    ],
    "benchmarks.SampleBenchmark.time_benchmark2": [ ... ],
    "benchmarks.SampleBenchmark.time_benchmark3": [ ... ],
    "benchmarks.SampleBenchmark.time_benchmark4": [ ... ]
  }
}
```

The shape the parser has to understand:

- **``result_columns``** is the positional schema. Each entry in
  ``results[<benchmark_name>]`` is a list whose elements correspond
  positionally to ``result_columns``. The parser must zip them together
  rather than look up by key. asv did this deliberately to keep result
  files small across many commits; the cost is that parsers cannot
  blindly read ``results["..."]["result"]`` — they have to compute the
  index of ``"result"`` in ``result_columns`` first and then index into
  the per-benchmark list.
- **``result``** — the headline timing value(s). For a non-parametric
  ``time_*`` benchmark this is a one-element list like ``[2.1500xxx]``.
  For parametric benchmarks (``params`` non-empty) it is a flat list in
  row-major order over the parameter grid. **Unit is seconds**, always,
  regardless of what the HTML dashboard renders.
- **``stats_*`` columns** — asv records a 99% confidence interval
  (``stats_ci_99_a`` / ``stats_ci_99_b``), inter-quartile range
  (``stats_q_25`` / ``stats_q_75``), and the raw repeat count
  (``stats_number`` / ``stats_repeat``). Each is a per-sample list with
  the same cardinality as ``result``.
- **``samples``** — the individual raw timings, or ``null`` when not
  retained. Can be large; treat as optional.
- **``profile``** — cProfile output, if profiling was requested. Almost
  always ``null`` in normal runs.
- **``duration``** — total wall time asv spent on this benchmark
  including repeats; not the per-call time. Do **not** emit this as the
  headline metric; it is of log-line interest, not the measurement.
- **``commit_hash`` / ``date``** — top-level. ``date`` is milliseconds
  since epoch, UTC. Per
  [`docs/design.md`](../../../docs/design.md#field-semantics), Nyrkiö
  ``timestamp`` is git-derived by the ingest layer; the parser sets
  ``timestamp: 0``. If the wall-clock ``date`` is worth preserving, stash
  it in ``extra_info["machine_time"]``. The ``commit_hash`` is **not**
  written into ``attributes["git_commit"]`` by the parser either — per
  the data model, git-related attributes are filled in by the ingest
  layer, not the parser.

Recommended parser mapping to Nyrkiö JSON:

- ``attributes["test_name"]`` — derived from the ``results`` key by
  taking the last path segment and stripping ``time_``. So
  ``benchmarks.SampleBenchmark.time_benchmark1`` →
  ``"benchmark1"``. (If asv's grouping/class hierarchy ever needs to
  appear in the parsed output, it belongs in
  ``extra_info["asv_benchmark_name"]`` or similar, not in
  ``attributes``.)
- **Headline metric: ``mean``** of the ``result`` values with
  ``unit: "s"``, ``direction: "lower_is_better"``. For a single-sample
  ``result`` list the mean is just that element.
- Additional metrics from the ``stats_*`` columns: emit ``ci99_low``
  (from ``stats_ci_99_a``) and ``ci99_high`` (from ``stats_ci_99_b``)
  alongside ``q25`` and ``q75`` from the quartile columns. All in
  seconds, ``lower_is_better``.
- ``extra_info`` — stash ``stats_number`` and ``stats_repeat`` for
  traceability, plus ``env_name`` and ``python`` from the top level if
  they help downstream consumers distinguish environments. Raw
  ``samples`` are too large to emit by default; leave them out.
- ``timestamp`` — set to ``0``.
- ``passed`` — always ``true`` in the captured fixture. asv encodes
  failures as a ``"failed"`` sentinel string in place of the numeric
  ``result``; if a parser ever sees that, it should record the test
  with ``passed: false`` and omit the numeric headline metric. Failing
  benchmarks are not the common case and the captured fixture is not
  expected to contain any.

### Reference-only prior art

asv did not have a parser in the predecessor TypeScript fork, so this
parser is being written from scratch against the real captured output.
