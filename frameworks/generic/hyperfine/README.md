# hyperfine

[hyperfine](https://github.com/sharkdp/hyperfine) is a modern command-line
benchmarking tool that runs a shell command many times and reports
statistics (mean, stddev, median, min, max, user/system). It's the
drop-in replacement for Unix `time` when you want statistics, not a
single measurement.

## Links

- **Sample benchmark** — [`benchmark1.sh`](benchmark1.sh),
  [`benchmark2.sh`](benchmark2.sh), [`benchmark3.sh`](benchmark3.sh),
  [`benchmark4.sh`](benchmark4.sh), orchestrated by [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/hyperfine.yml`](../../../.github/workflows/hyperfine.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/hyperfine.yml>
- **Parser (JSON)** — [`src/benchzoo/parsers/hyperfine_json.py`](../../../src/benchzoo/parsers/hyperfine_json.py) *(not yet written — pending a real captured fixture)*
- **Parser (CSV)** — [`src/benchzoo/parsers/hyperfine_csv.py`](../../../src/benchzoo/parsers/hyperfine_csv.py) *(not yet written — pending a real captured fixture)*
- **Parser (Markdown)** — markdown export is a pipe-delimited table with the same stats; it is too lossy for a real parser (no per-run `times`, no `exit_codes`, values rounded for display) and is captured only as a human-readable reference.
- **Parser tests** — [`tests/parsers/test_hyperfine.py`](../../../tests/parsers/test_hyperfine.py) *(not yet written)*

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) in
hyperfine idiom:

- **Test 1** (sleep 2.15 s) — [`benchmark1.sh`](benchmark1.sh) runs
  `sleep 2.15`; hyperfine reports ~2.15 s mean wall time.
- **Test 2** (tight CPU loop) — [`benchmark2.sh`](benchmark2.sh) runs a
  bash `for ((i=0; i<1000; i++)); do :; done`. Bash is interpreted, so
  the loop is not optimized away and no `black_box` equivalent is
  needed. Note that hyperfine's minimum measurable time is bounded by
  process startup overhead (a few ms on typical Linux runners), so
  test 2's reported duration is dominated by bash startup, not the
  loop itself. That's fine — the purpose of test 2 is to verify the
  parser handles small values, and "small for hyperfine" is a few
  milliseconds.
- **Test 3** (write 1.4 MB to /dev/null) — [`benchmark3.sh`](benchmark3.sh)
  runs `head -c 1400000 /dev/urandom > /dev/null`.
- **Test 4** (monthly change point) — [`benchmark4.sh`](benchmark4.sh)
  computes `2.15 + ((month mod 3) - 1)` in UTC and sleeps for that
  many seconds.

The orchestration lives in [`run.sh`](run.sh), which invokes hyperfine
once with all four commands and `--export-json output.json --export-csv
output.csv --export-markdown output.md`. Keeping the
hyperfine invocation in a shell script (rather than inline in the
workflow YAML) makes it easy to iterate locally via `act` or a direct
`./run.sh`.

## Running locally

```bash
act push -W .github/workflows/hyperfine.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/hyperfine-output/` (`output.json`,
`output.csv`, `output.md`). See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with hyperfine installed locally, you can bypass `act`
entirely and just run `./run.sh` from this directory. That produces the
same `output.json`, `output.csv`, and `output.md` but without the GitHub Actions artifact plumbing.

## Parser notes

hyperfine supports three export formats, all produced in a single run:

- **JSON** (`--export-json`) — the richest format; described in detail below.
- **CSV** (`--export-csv`) — columns: `command,mean,stddev,median,user,system,min,max`. Values are in seconds. Each row is one command. This is a flat table with no per-run `times` or `exit_codes`, but all summary statistics are present and machine-readable. Parsed by a dedicated `hyperfine_csv` module.
- **Markdown** (`--export-markdown`) — a pipe-delimited table with the same summary statistics. Useful as a human-readable reference but too lossy for a real parser (values are rounded for display, no `exit_codes`). Captured in the artifact for reference only.

### JSON format

hyperfine's `--export-json` format is well-defined and stable. Each
entry under `results[]` carries:

- `command` — the exact shell string or (if `--command-name` was used)
  the provided name. We use `--command-name` in `run.sh`, so this field
  holds `"benchmark1"` .. `"benchmark4"` and maps directly to
  `attributes["test_name"]`.
- `mean`, `stddev`, `median`, `user`, `system`, `min`, `max` — all in
  seconds, as floating-point numbers. These become `metrics[]` entries
  with `unit: "s"`.
- `times` — the full array of per-run wall times, also in seconds.
  Optional to emit as a metric; parsers may choose to keep it in
  `extra_info` for reference, or drop it. Recommendation: drop it from
  `metrics` (it's raw per-run data, not a summary statistic) and do not
  stash it in `extra_info` either — the captured fixture on disk is the
  canonical record of the raw runs.
- `exit_codes` — non-zero entries indicate failing runs. If any run
  failed, set `passed: false` on the test-results dict and leave the
  metric values as hyperfine reports them (mean/stddev of the
  still-completed runs).

`direction` for hyperfine metrics is always `"lower_is_better"` — every
value hyperfine reports is a duration.
