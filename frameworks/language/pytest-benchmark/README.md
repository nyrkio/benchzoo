# pytest-benchmark

[pytest-benchmark](https://github.com/ionelmc/pytest-benchmark) is the
most popular Python micro-benchmarking tool. It plugs into pytest and
exposes a ``benchmark`` fixture that times a callable across many
rounds, auto-calibrating the iteration count to the test's duration,
and emits a well-defined JSON report with min/max/mean/stddev/median/
iqr/ops per test.

## Links

- **Sample benchmark** — see [`test_sample_benchmark.py`](test_sample_benchmark.py)
- **Workflow** — [`.github/workflows/pytest-benchmark.yml`](../../../.github/workflows/pytest-benchmark.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/pytest-benchmark.yml>
- **Parser (JSON)** — [`src/benchzoo/parsers/pytest_benchmark_json.py`](../../../src/benchzoo/parsers/pytest_benchmark_json.py) *(not yet written — pending a real captured fixture)*
- **Parser (junitxml)** — [`src/benchzoo/parsers/junit_pytest.py`](../../../src/benchzoo/parsers/junit_pytest.py) *(not yet written)*
- **Parser tests** — [`tests/parsers/test_pytest_benchmark.py`](../../../tests/parsers/test_pytest_benchmark.py) *(not yet written)*

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) in
pytest-benchmark idiom. Each of the four tests is a plain pytest
function taking the ``benchmark`` fixture; the function name
(``test_benchmark1`` .. ``test_benchmark4``) maps directly to the test
identifier the parser will write into ``attributes["test_name"]``.

- **Test 1** (sleep 2.15 s) — calls ``time.sleep(2.15)`` inside the
  benchmarked callable. pytest-benchmark reports this with ~5 rounds by
  default, each round a single call. Group: ``sleep``.
- **Test 2** (tight CPU loop) — a bare ``for _ in range(1000): pass``.
  Python is interpreted and does not eliminate empty loops, so no
  ``black_box`` mechanism is needed. pytest-benchmark auto-calibrates
  the inner iteration count so each round takes a measurable amount of
  time. Group: ``compute``.
- **Test 3** (write 1.4 MB to /dev/null) — draws
  ``os.urandom(1_400_000)`` and writes it to ``/dev/null`` opened in
  ``"wb"`` mode. The urandom draw is included in the timed region,
  matching the bash reference's
  ``head -c 1400000 /dev/urandom > /dev/null``. Group: ``compute``.
- **Test 4** (monthly change point) — computes
  ``sleep_s = 2.15 + ((month % 3) - 1)`` where ``month`` is read from
  ``datetime.datetime.now(datetime.timezone.utc).month`` (UTC, per the
  spec) and sleeps for that many seconds. Produces the step-function
  series described in the canonical sample benchmark. Group: ``sleep``.

Tests are assigned to **groups** via
``@pytest.mark.benchmark(group=...)``. This exercises the ``group``
field in the JSON output; the parser should record it as
``extra_info["group"]`` (see
[design.md's extra_info docs](../../../docs/design.md#field-semantics)).
Downstream UIs can use groups for drill-down navigation or graph
organization.

### Output formats captured

The workflow captures **two** output formats:

1. **JSON** (``--benchmark-json=output.json``) — the primary
   machine-readable format. Rich statistics per benchmark.
2. **JUnit XML** (``--junitxml=output-junit.xml``) — pytest's standard
   XML report, augmented by pytest-benchmark with ``<properties>``
   entries carrying benchmark stats. Exercises the ``junit_pytest``
   parser (one of the per-producer junit parsers described in
   [`parser-targets.md`](../../../docs/parser-targets.md#6-unit-test--qa-frameworks-per-test-duration)).

Both are uploaded in the same ``pytest-benchmark-output`` artifact.

## Running locally

```bash
act push -W .github/workflows/pytest-benchmark.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/pytest-benchmark-output/output.json`.
See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with the requirements installed locally, you can skip
`act` entirely and run

```bash
pip install -r requirements.txt
pytest test_sample_benchmark.py --benchmark-json=output.json
```

from this directory. That produces the same `output.json` but without
the GitHub Actions artifact plumbing.

## Parser notes

pytest-benchmark's ``--benchmark-json`` output is a single JSON
document. The top-level keys of interest for the parser are
``machine_info``, ``commit_info``, ``datetime``, ``version`` and
``benchmarks``. The ``benchmarks`` field is the important one: a list
with one entry per pytest test function, each entry shaped roughly
like:

```json
{
  "group": "sleep",
  "name": "test_benchmark1",
  "fullname": "test_sample_benchmark.py::test_benchmark1",
  "params": null,
  "param": null,
  "extra_info": {},
  "options": { "disable_gc": false, "timer": "perf_counter", ... },
  "stats": {
    "min":        2.1500xxx,
    "max":        2.1501xxx,
    "mean":       2.1500xxx,
    "stddev":     0.00001x,
    "rounds":     5,
    "median":     2.1500xxx,
    "iqr":        0.0000xx,
    "q1":         2.1500xxx,
    "q3":         2.1500xxx,
    "iqr_outliers":    0,
    "stddev_outliers": 1,
    "outliers":        "1;0",
    "ld15iqr":    2.1500xxx,
    "hd15iqr":    2.1500xxx,
    "ops":        0.4651xxx,
    "total":     10.7502xxx,
    "iterations": 1
  }
}
```

All of ``min``, ``max``, ``mean``, ``stddev``, ``median``, ``iqr``,
``q1``, ``q3``, ``total`` are in **seconds** (pytest-benchmark's native
unit — regardless of how the terminal pretty-printer renders them). The
``ops`` field is operations per second, i.e. the reciprocal of the
per-iteration mean.

Recommended parser mapping to Nyrkiö JSON:

- ``attributes["test_name"]`` — derived from ``benchmarks[i].name`` by
  stripping the ``test_`` prefix (so ``test_benchmark1`` →
  ``"benchmark1"``).
- ``extra_info["group"]`` — from ``benchmarks[i].group``. The sample
  benchmark assigns tests to groups (``"sleep"``, ``"compute"``) via
  ``@pytest.mark.benchmark(group=...)``. The ``group`` field belongs in
  ``extra_info`` (not ``attributes``) because it is optional
  classification metadata, not an identity key. Downstream UIs can use
  it to let users select a group first and then drill into tests within
  that group, or to organize tests onto separate graphs. If ``group``
  is ``null`` (user didn't set one), omit the key from ``extra_info``.
- **Headline metric: ``mean``.** Emit one ``metrics`` entry with
  ``name: "mean"``, ``unit: "s"``, ``direction: "lower_is_better"``,
  ``value: stats.mean``. The choice between ``mean`` and ``min`` is a
  judgment call — pytest-benchmark itself does not pick one. ``min`` is
  the more stable number on noisy systems (you see the "fastest
  possible" run, uncontaminated by scheduler jitter and GC pauses), but
  ``mean`` is the conventional summary statistic and matches what most
  downstream dashboards expect. We standardize on **``mean``** so that
  reports across frameworks agree on "headline = mean", and emit all
  the other statistics as extra metrics so downstream consumers that
  prefer ``min`` can pick it up without a second parse.
- Additional metrics emitted alongside ``mean`` (all ``unit: "s"``,
  ``direction: "lower_is_better"``):
  ``min``, ``max``, ``stddev``, ``median``.
- ``ops`` (throughput) — emit with
  ``unit: "ops/s"``, ``direction: "higher_is_better"``. It is redundant
  with ``mean`` (``ops == 1 / mean``) but free to include and useful
  for consumers that want throughput natively.
- ``timestamp`` — set to ``0``. Do **not** use the top-level
  ``datetime`` field from the JSON as the Nyrkiö timestamp; per
  [`docs/design.md`](../../../docs/design.md#field-semantics), Nyrkiö
  ``timestamp`` is git-derived, not wall-clock. If the wall-clock value
  is worth preserving, stash it in ``extra_info["machine_time"]``.
- ``extra_info`` — the benchmark's own ``extra_info`` dict is
  pass-through if non-empty; ``params``/``param`` similarly (they carry
  parametrization when the test uses ``@pytest.mark.parametrize``). This
  corpus does not use either, so both will be empty/``null`` in the
  captured fixture, but the parser should handle them on general
  principle.
- ``passed`` — always ``true`` in the captured fixture. pytest-benchmark
  only writes a benchmark entry if the underlying test passed; failing
  tests are omitted from ``benchmarks[]`` entirely, so there is no
  per-benchmark pass/fail field to read. If a test fails, the parser
  will simply not see it. *(This is a known asymmetry versus, e.g.,
  hyperfine, which reports exit codes per run.)*

Unit is **always seconds** in the JSON; the terminal pretty-printer's
``ms``/``us`` display is a rendering convention and does not change the
underlying field. Parsers should emit ``unit: "s"`` without any
rescaling.

### Reference-only prior art

The TypeScript fork at
[nyrkio/change-detection](https://github.com/nyrkio/change-detection)
shipped a pytest-benchmark parser. It is **reference-only** (see
[`docs/design.md`](../../../docs/design.md#what-this-is)) — we do not
port the code, but its output field mapping is useful as a second
opinion when the Python parser is finally written.
