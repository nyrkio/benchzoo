# phpbench

[PHPBench](https://phpbench.readthedocs.io) is the standard benchmarking
framework for PHP. It discovers bench classes, runs each ``bench*``
subject across a configurable number of revolutions and iterations, and
emits reports in text, XML, CSV, JSON, or HTML. The XML ``--dump-file``
format preserves per-iteration timings; the built-in reports
(``default``, ``aggregate``, ``compare``, ...) render summary statistics
in whichever output format is selected.

## Links

- **Sample benchmark** — see [`benchmarks/SampleBench.php`](benchmarks/SampleBench.php)
- **Workflow** — [`.github/workflows/phpbench.yml`](../../../.github/workflows/phpbench.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/phpbench.yml>
- **Parser (XML)** — [`src/benchzoo/parsers/phpbench_xml.py`](../../../src/benchzoo/parsers/phpbench_xml.py) *(not yet written — pending a real captured fixture)*
- **Parser (JSON)** — [`src/benchzoo/parsers/phpbench_json.py`](../../../src/benchzoo/parsers/phpbench_json.py) *(not yet written)*
- **Parser tests** — [`tests/parsers/test_phpbench.py`](../../../tests/parsers/test_phpbench.py) *(not yet written)*

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) in
PHPBench idiom. The four tests are bench methods on a single
``SampleBench`` class; each method is named ``benchBenchmarkN``, chosen
so a parser can map directly from the PHPBench subject name
``benchBenchmark1`` to ``attributes["test_name"] = "benchmark1"`` by
stripping the ``bench`` prefix and lower-casing the first character.

- **Test 1** (sleep 2.15 s) — ``usleep(2_150_000)``. Annotated
  ``@Revs(1) @Iterations(3)`` to bound wall time — PHPBench's default
  calibration would otherwise run the 2.15 s sleep many times over.
  Group: ``sleep``.
- **Test 2** (tight CPU loop) — ``for ($i = 0; $i < 1000; $i++) {}``.
  PHP is interpreted and does not eliminate empty loops, so no
  ``black_box`` mechanism is needed. Annotated ``@Revs(1000)`` so each
  iteration aggregates 1000 runs of the loop, producing a measurable
  per-rev time. Group: ``compute``.
- **Test 3** (write 1.4 MB to /dev/null) — draws
  ``random_bytes(1_400_000)`` and writes it to ``/dev/null`` via
  ``fwrite``. Group: ``compute``.
- **Test 4** (monthly change point) — computes
  ``sleep_s = 2.15 + ((month % 3) - 1)`` where ``month`` is UTC
  (``gmdate('n')``) and sleeps for that many seconds via
  ``usleep((int) round($sleepS * 1_000_000))``. Produces the
  step-function series described in the canonical sample benchmark.
  Group: ``sleep``.

Tests are assigned to **groups** via ``@Groups({"..."})``. This
exercises the ``groups`` field in PHPBench's output; the parser should
record the (single) group as ``extra_info["group"]`` (see
[design.md's extra_info docs](../../../docs/design.md#field-semantics)).

### Annotation style

The sample uses **docblock** annotations (``@Revs(1)``,
``@Iterations(3)``, ``@Groups({"sleep"})``). PHPBench 1.3 also supports
PHP 8 native attributes (``#[Bench]``, ``#[Revs(1)]``,
``#[Iterations(3)]``, ``#[Groups(['sleep'])]``), but docblocks are
chosen here because they:

- work identically across PHP 7.4..8.x, so the benchmark file is
  portable regardless of the host runtime,
- match the style used in the bulk of real-world PHPBench benchmarks
  in the ecosystem, which is more representative of what parsers will
  actually see in user-provided fixtures.

### Output formats captured

The workflow captures **three** output files:

1. **XML** (``--dump-file=output.xml``) — PHPBench's native suite dump.
   Rich, per-iteration detail. This is the primary machine-readable
   format.
2. **JSON** (``--report=aggregate --output='json:path=output.json'``) —
   the ``aggregate`` report rendered as JSON. One summary row per
   subject/variant.
3. **Text** (``tee output.txt``) — the default console report. Useful
   as a smoke-test fixture and as human-readable reference.

All three are uploaded in the same ``phpbench-output`` artifact.

## Running locally

```bash
act push -W .github/workflows/phpbench.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/phpbench-output/`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with PHP 8.3 and Composer installed locally, you can
skip `act` entirely and run

```bash
./run.sh
```

from this directory. That produces the same `output.xml`, `output.json`
and `output.txt` but without the GitHub Actions artifact plumbing.

## Parser notes

PHPBench's native XML dump is structured as:

```
<phpbench version="...">
  <suite ...>
    <benchmark class="BenchzooSample\SampleBench">
      <subject name="benchBenchmark1">
        <variant ...>
          <iteration time-net="2150123" ... />
          <iteration time-net="2150456" ... />
          <iteration time-net="2150234" ... />
        </variant>
      </subject>
      ...
    </benchmark>
  </suite>
</phpbench>
```

Key points for the parser:

- **Per-iteration time is in microseconds.** The ``time-net``
  attribute on ``<iteration>`` is the net (user-code-only) elapsed
  time in integer microseconds. To get test 1's ~2.15 s back you
  divide by 1,000,000 — i.e. the number you'll grep for is ``2150000``
  (or thereabouts), not ``2.15``.
- **Mean / min / max are not emitted at the XML level** — they are
  computed at report-generation time. The parser must aggregate the
  ``<iteration>`` elements within a ``<variant>`` itself: mean is the
  arithmetic mean of ``time-net`` values, min/max are the extremes.
  (Alternatively, use the ``output.json`` fixture which contains
  already-aggregated values — see below.)
- **Subject name → test_name.** Strip the ``bench`` prefix from
  ``<subject name="...">`` and lower-case the first character:
  ``benchBenchmark1`` → ``"benchmark1"``.
- **Group.** Each ``<subject>`` has ``<group name="..."/>`` children
  (one per ``@Groups`` entry). This corpus assigns exactly one group
  per subject, so record it as ``extra_info["group"]``. If multiple
  groups are present in real-world fixtures, record the list as-is or
  pick the first — parser author's call; document the choice.
- **Revs and iterations.** ``<variant sleep="..." ...>`` carries a
  ``revs`` attribute and the number of ``<iteration>`` children is the
  iteration count. Record as ``extra_info["revs"]`` and
  ``extra_info["iterations"]`` respectively.

The JSON aggregate output has a different shape — it is driven by
PHPBench's report generators, so the top-level structure is the
``aggregate`` report's rows rather than the full suite tree. Each row
carries pre-computed ``mean``, ``min``, ``max``, ``mode``, ``rstdev``,
``stdev``, and so on, with the subject name in the ``subject`` column.
This is the easier format to parse if per-iteration detail is not
needed.

Recommended parser mapping to Nyrkiö JSON (XML parser):

- ``attributes["test_name"]`` — derived from ``<subject name>`` as
  described above.
- ``extra_info["group"]`` — from ``<group name>`` under the subject.
  Omit if absent.
- ``extra_info["revs"]`` — integer, from ``<variant revs="...">``.
- ``extra_info["iterations"]`` — integer, the number of
  ``<iteration>`` children.
- **Headline metric: ``mean``.** Emit one ``metrics`` entry with
  ``name: "mean"``, ``unit: "s"``, ``direction: "lower_is_better"``,
  ``value: mean(time-net) / 1_000_000`` (convert microseconds to
  seconds so all benchzoo parsers agree on the unit).
- Additional metrics: ``min``, ``max``, ``stddev``, all ``unit: "s"``,
  all ``direction: "lower_is_better"``, computed from the per-iteration
  ``time-net`` values.
- ``timestamp`` — always ``0``. PHPBench's suite XML embeds a
  ``date="..."`` attribute on ``<suite>``; per
  [`docs/design.md`](../../../docs/design.md#field-semantics), Nyrkiö
  ``timestamp`` is git-derived, not wall-clock. If the wall-clock value
  is worth preserving, stash it in ``extra_info["machine_time"]``.
- ``passed`` — PHPBench does not emit a per-iteration pass/fail flag
  in the XML dump for non-assertion subjects. If the ``<iteration>``
  carries an ``exception`` child or the subject has a ``<error>``
  child, mark ``passed: false``; otherwise ``true``.

Units: **always convert to seconds** at the parser boundary. The XML's
native unit is microseconds (``time-net``) and the JSON aggregate
report's values are also microseconds by default. Emit ``unit: "s"``
after dividing by 1,000,000.
