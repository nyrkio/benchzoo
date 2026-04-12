# custom-csv (generic CSV escape hatch)

A generic CSV format defined by benchzoo itself — **not** the output of
any third-party benchmark tool. It exists so a user whose tooling isn't
covered by a framework-specific parser can dump their numbers into a
simple header-plus-rows CSV and hand that to benchzoo. Inherited
conceptually from [`nyrkio/change-detection`][fork].

[fork]: https://github.com/nyrkio/change-detection

Because this is a "framework we made up," the sample benchmark here is
not a real measurement — it's a script that emits the canonical
[sample-benchmark](../../../docs/sample-benchmark.md) ground-truth
values in the CSV format, so parser tests have an exemplar fixture to
consume.

## Links

- **Sample benchmark** — [`emit.sh`](emit.sh)
- **Workflow** — [`.github/workflows/custom-csv.yml`](../../../.github/workflows/custom-csv.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/custom-csv.yml>
- **Parser** — [`src/benchzoo/parsers/custom_csv.py`](../../../src/benchzoo/parsers/custom_csv.py) *(not yet written — pending a real captured fixture)*
- **Parser tests** — [`tests/parsers/test_custom_csv.py`](../../../tests/parsers/test_custom_csv.py) *(not yet written)*

## Sample benchmark

[`emit.sh`](emit.sh) writes `output.csv` with the canonical four tests:

- **Test 1** (sleep 2.15 s) — four rows: `mean`, `min`, `max`, `stddev`
  (all seconds, lower_is_better). The mean is the exact canonical
  ground truth; the min/max/stddev are plausible-looking synthetic
  values around it.
- **Test 2** (tight CPU loop) — three rows: `mean`, `min`, `max` in
  microseconds.
- **Test 3** (write 1.4 MB to /dev/null) — three latency rows
  (`mean`, `min`, `max` in milliseconds) plus one throughput row
  (`throughput`, `MB/s`, `higher_is_better`). This demonstrates that a
  single test can carry metrics with **different units and different
  directions** — the escape hatch does not force everything to one axis.
- **Test 4** (monthly change point) — a `mean` row whose value follows
  the same monthly formula as hyperfine's
  [`benchmark4.sh`](../hyperfine/benchmark4.sh)
  (`2.15 + ((month mod 3) - 1)` in UTC), plus a `month` row with an
  empty `unit` and empty `direction` to exercise the "fields are
  optional" path.

None of these are measured — they're hard-coded to the canonical
ground-truth values so the parsers have something to exercise against.

## Running locally

```bash
act push -W .github/workflows/custom-csv.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/custom-csv-output/output.csv`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, just run `./emit.sh` directly from this directory — no
runtime or toolchain is needed.

## Parser notes

Input format: a CSV with a **required** header row followed by one data
row per (test, metric) pair.

```csv
test_name,metric_name,unit,value,direction
benchmark1,mean,s,2.15,lower_is_better
benchmark1,min,s,2.14,lower_is_better
benchmark2,mean,us,50,lower_is_better
benchmark3,throughput,MB/s,1400,higher_is_better
```

Column semantics:

| Column        | Required | Notes                                                                                      |
| ------------- | -------- | ------------------------------------------------------------------------------------------ |
| `test_name`   | yes      | Non-empty string. Becomes `attributes["test_name"]`.                                       |
| `metric_name` | yes      | Non-empty string. Becomes `metrics[i]["name"]`.                                            |
| `unit`        | no       | May be empty. When non-empty, becomes `metrics[i]["unit"]` verbatim.                        |
| `value`       | yes      | Parsed as float. Becomes `metrics[i]["value"]`.                                            |
| `direction`   | no       | Either `"higher_is_better"`, `"lower_is_better"`, or empty. Empty means omit the key.      |

Mapping to Nyrkiö JSON (grouping by `test_name`):

- Rows with the same `test_name` are collected into one Nyrkiö JSON
  dict. Order within the `metrics[]` array follows the row order in
  the CSV.
- Each row becomes one entry in that dict's `metrics[]` array.
- `direction` is per-metric. A single test can mix
  `lower_is_better` latency rows with `higher_is_better` throughput
  rows; the parser must not force them to a single direction.
- Empty `unit` on a row means the parser omits the `unit` key on that
  metric entry (the Nyrkiö shape allows `unit` to be absent when the
  measurement is unitless, e.g. a count).
- Empty `direction` on a row means the parser omits the `direction`
  key on that metric entry (see
  [`design.md`](../../../docs/design.md#field-semantics): "Omit (don't
  set to `null`) when unknown.").
- `timestamp` is always `0` (parsers never synthesize it). `passed`
  defaults to `true`; the CSV has no failure-marking column. Git
  attributes are left out.

The CSV escape hatch is strictly more expressive than the JSON escape
hatches in two ways: it supports **multiple metrics per test** (the
JSON format is one-metric-per-entry), and it supports **per-metric
direction mixing** within a single test (the JSON format fixes the
direction globally by variant). Users with richer data should prefer
this format.

## Dialect notes for parser implementers

- **Delimiter:** comma only. No semicolon fallback, no tab fallback.
  Users whose tool emits a different delimiter are expected to
  preprocess.
- **Quoting:** standard CSV quoting rules (RFC 4180). Fields
  containing commas or newlines must be double-quoted, with embedded
  quotes escaped as `""`. Python's stdlib `csv.DictReader` handles
  this correctly by default.
- **Header row:** required. The header **must** contain exactly these
  five column names (case-sensitive) in any order; the parser keys off
  `DictReader`'s header detection rather than column position, so
  reordering the columns is allowed but renaming them is not.
- **Trailing newline:** optional. Blank lines at EOF are ignored.
- **Comments:** not supported. Any line that isn't the header or a
  valid data row is an error.
