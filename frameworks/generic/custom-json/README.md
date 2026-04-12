# custom-json (customBiggerIsBetter / customSmallerIsBetter)

Two JSON escape-hatch formats defined by benchzoo itself — **not** the
output of any third-party benchmark tool. They exist so that a user with
a bespoke benchmarking script can convert their numbers to one of these
simple shapes and hand them to benchzoo instead of writing a new parser.
The formats are inherited conceptually from
[`nyrkio/change-detection`][fork], which in turn inherited the object
shape from [`benchmark-action/github-action-benchmark`][upstream].

[fork]: https://github.com/nyrkio/change-detection
[upstream]: https://github.com/benchmark-action/github-action-benchmark

Because these are "frameworks we made up," the sample benchmark here is
not a real measurement — it's a script that emits the canonical
[sample-benchmark](../../../docs/sample-benchmark.md) ground-truth
values in each format, so parser tests have exemplar fixtures to
consume.

## Links

- **Sample benchmark** — [`emit.sh`](emit.sh)
- **Workflow** — [`.github/workflows/custom-json.yml`](../../../.github/workflows/custom-json.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/custom-json.yml>
- **Parser** — [`src/benchzoo/parsers/custom_json.py`](../../../src/benchzoo/parsers/custom_json.py) *(not yet written — pending a real captured fixture)*
- **Parser tests** — [`tests/parsers/test_custom_json.py`](../../../tests/parsers/test_custom_json.py) *(not yet written)*

## Sample benchmark

[`emit.sh`](emit.sh) generates two files:

- `output-smaller.json` — the `customSmallerIsBetter` variant. Every
  value is a duration (wall time, latency) — smaller is better.
- `output-bigger.json` — the `customBiggerIsBetter` variant. Every
  value is a rate or score — bigger is better.

Both files contain the same four canonical tests with ground-truth
values:

- **Test 1** (sleep 2.15 s) — emitted as `2.15 s` in the smaller
  variant, and as `0.4651 runs/s` (1 run per 2.15 s) in the bigger
  variant.
- **Test 2** (tight CPU loop) — emitted as `50 us` / `20000 ops/s`.
- **Test 3** (write 1.4 MB to /dev/null) — emitted as `1.0 ms` /
  `1400 MB/s`.
- **Test 4** (monthly change point) — the script computes
  `2.15 + ((month mod 3) - 1)` in UTC using the same awk formula as
  hyperfine's [`benchmark4.sh`](../hyperfine/benchmark4.sh). The
  smaller variant reports the sleep duration in seconds; the bigger
  variant reports its reciprocal as `runs/s`.

None of these are measured — they're hard-coded to the canonical
ground-truth values so the parsers have something to exercise against.
That's the whole point: the escape hatch parsers must round-trip
known-good numbers without distortion.

## Running locally

```bash
act push -W .github/workflows/custom-json.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/custom-json-output/`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, just run `./emit.sh` directly from this directory — no
runtime or toolchain is needed.

## Parser notes

Input format: a JSON array of objects, each with `name`, `unit`,
`value`, and optionally `extra`:

```json
[
  {"name": "benchmark1", "unit": "s",     "value": 2.15,  "extra": "..."},
  {"name": "benchmark2", "unit": "us",    "value": 50,    "extra": "..."},
  {"name": "benchmark3", "unit": "ms",    "value": 1.0,   "extra": "..."},
  {"name": "benchmark4", "unit": "s",     "value": 2.15,  "extra": "..."}
]
```

The **only difference** between `customBiggerIsBetter` and
`customSmallerIsBetter` is the direction assigned to every metric. The
on-disk shape is identical; the format name is carried out-of-band (by
filename, by an ingest-time parameter, or by convention — benchzoo
parsers take the direction as an argument rather than auto-detecting
it, since the file itself doesn't distinguish the two variants).

Mapping to Nyrkiö JSON (one dict per array entry):

| Input field | Nyrkiö JSON destination                                      |
| ----------- | ------------------------------------------------------------ |
| `name`      | `attributes["test_name"]` **and** `metrics[0]["name"]`       |
| `unit`      | `metrics[0]["unit"]` (verbatim — no normalization)           |
| `value`     | `metrics[0]["value"]` (as-is numeric)                        |
| `extra`     | `extra_info["extra"]` if present, omitted otherwise          |

`direction` on every metric is fixed by the format variant:

- `customBiggerIsBetter`  → `direction: "higher_is_better"`
- `customSmallerIsBetter` → `direction: "lower_is_better"`

`timestamp` is always `0` (parsers never synthesize it — see
[`design.md`](../../../docs/design.md#field-semantics)). `passed` defaults
to `true`; the format has no failure-marking field. Git-related
attributes (`git_repo`, `branch`, `git_commit`) are left out entirely.

There is only one metric per entry, because the format has no grouping
concept — every `{name, unit, value}` row is its own independent
measurement. A test with four statistics (mean, min, max, stddev) would
appear as four array entries, each with its own `name` like
`"benchmark1.mean"`, `"benchmark1.min"`, etc. The parser does not try to
group them; users who want grouped metrics should use the CSV escape
hatch instead (which has an explicit `test_name` / `metric_name`
split).
