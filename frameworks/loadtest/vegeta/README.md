# vegeta

[vegeta](https://github.com/tsenart/vegeta) is Tomás Senart's Go HTTP
load testing tool. It drives a configurable constant request rate at
one or more HTTP targets for a configurable duration and records each
request's timing and result into a compact binary log. A separate
`vegeta report` step reduces that log into a text, JSON, or histogram
report. Unlike wrk, vegeta defaults to a constant-rate attack model
(corrects for coordinated omission) and emits a well-defined JSON
shape — making it a cleaner parser target than wrk's text-only output.

## Links

- **Sample benchmark** — a minimal static page ([`index.html`](index.html))
  served by [`nginx.conf`](nginx.conf), attacked by [`run.sh`](run.sh)
  against [`targets.txt`](targets.txt)
- **Workflow** — [`.github/workflows/vegeta.yml`](../../../.github/workflows/vegeta.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/vegeta.yml>
- **Parser** — [`src/benchzoo/parsers/vegeta.py`](../../../src/benchzoo/parsers/vegeta.py) *(not yet written — pending a real captured fixture)*
- **Parser tests** — [`tests/parsers/test_vegeta.py`](../../../tests/parsers/test_vegeta.py) *(not yet written)*

## Sample benchmark

vegeta does not fit the
[canonical sample benchmark](../../../docs/sample-benchmark.md) cleanly.
The canonical suite was designed for frameworks that time arbitrary
code (a sleep, a CPU loop, an I/O write), and the four tests exist to
stress-test parsers across very different magnitudes. vegeta is a
fundamentally different kind of tool: a single invocation measures
one HTTP endpoint's behavior under sustained constant-rate load, and
the latency numbers are emergent properties of nginx + the kernel's
TCP stack + the runner's CPU and scheduling — not a quantity under
our control. Trying to shoehorn `sleep 2.15` into a p99 latency is
nonsensical.

So the adaptation is explicit and honest: **one test run, not four.**
This mirrors the deviation already taken by the
[`lighthouse`](../../frontend/lighthouse/) and [`wrk`](../wrk/)
frameworks, which had the same structural mismatch.

- **Test 1** (sleep 2.15 s) — **dropped.** vegeta does not measure
  arbitrary sleep; it measures HTTP request latency under a
  constant-rate attack. There is no corresponding invocation.
- **Test 2** (tight CPU loop, sub-ms) — **dropped.** HTTP request
  latencies over loopback run in the tens-to-hundreds of microseconds
  range, not sub-microsecond. There is no sub-ms metric to exercise
  in vegeta's output.
- **Test 3** (write 1.4 MB to /dev/null) — **dropped.** vegeta
  reports `bytes_in` and `bytes_out` totals, but these are emergent
  from the attack duration, rate, and nginx's response size; we
  don't control them precisely enough to assert on a 1,400,000-byte
  value.
- **Test 4** (monthly change point) — **dropped.** Test 4 requires
  the measured quantity to be under our control so we can produce a
  deterministic monthly step function. vegeta's numbers depend on
  the runner and cannot be shaped into `2.15 + ((m mod 3) - 1)`.
  There is therefore no `schedule:` trigger on this workflow: it
  runs on push/PR and manual dispatch only.

What the framework *does* run is a single vegeta attack against a
single static nginx endpoint:

```
vegeta attack -duration=5s -rate=100/s -targets=targets.txt > results.bin
vegeta report -type=json results.bin > output.json
vegeta report           results.bin > output.txt
vegeta report -type=hist '[0,10ms,50ms,100ms,500ms]' results.bin > output-histogram.txt
```

That is: a 5-second attack at a steady 100 requests/sec against the
single target `GET http://localhost:8080/` (see
[`targets.txt`](targets.txt)), producing ~500 request samples in
the binary `results.bin`. We treat the whole run as one test with
`attributes["test_name"] = "homepage"`, and emit every headline
number vegeta reports — latency percentiles, throughput, success
ratio, status codes — as separate entries in `metrics[]`.

The page itself ([`index.html`](index.html)) is deliberately small —
a few hundred lines of static HTML with inline CSS — so nginx's
sendfile path does the work and vegeta's response-body parsing is
not the bottleneck. No external assets, no scripts, no cookies:
everything vegeta sees is committed in this directory.

The orchestration lives in [`run.sh`](run.sh), which:

1. Starts `nginx -p $(pwd) -c nginx.conf` in the foreground,
   backgrounded by `&`, so it uses the local directory for its pid
   file, error log, and temp directories (no `sudo`, no
   `/var/lib/nginx`).
2. `trap`s a kill on the nginx PID so it goes away on any exit.
3. Waits a moment with a `curl` loop for nginx to bind.
4. Runs `vegeta attack` writing `results.bin`.
5. Invokes `vegeta report` three times to produce JSON, text, and
   histogram renderings of that same binary log.

## Running locally

```bash
act push -W .github/workflows/vegeta.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/vegeta-output/`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with `vegeta` and `nginx` installed locally (vegeta is
easiest via `go install github.com/tsenart/vegeta/v12/cmd/vegeta@latest`
or a release tarball from GitHub), you can bypass `act` entirely and
just run `./run.sh` from this directory. That produces the same
output files without the GitHub Actions artifact plumbing.

## Parser notes

vegeta emits a well-defined JSON report via `vegeta report
-type=json`, plus a stable human-readable text report and a
bucketed histogram. Three captured output files land in the
artifact:

- `output.json` — the primary parser target.
- `output.txt` — the default text report; useful as a secondary
  parser format and trivially human-readable.
- `output-histogram.txt` — bucketed request-count histogram across
  a handful of latency ranges; informational.

### The vegeta JSON schema

A typical `vegeta report -type=json` payload looks like:

```json
{
  "latencies": {
    "total":     10234567890,
    "mean":      2034567,
    "50th":      1892345,
    "95th":      3124567,
    "99th":      5623421,
    "max":       8234567,
    "min":       1234567
  },
  "bytes_in":    { "total": 1234567, "mean": 2469.134 },
  "bytes_out":   { "total": 0,       "mean": 0 },
  "earliest":    "2026-04-13T12:00:00.000000000Z",
  "latest":      "2026-04-13T12:00:04.990000000Z",
  "end":         "2026-04-13T12:00:04.992345678Z",
  "duration":    4990000000,
  "wait":        2345678,
  "requests":    500,
  "rate":        100.04,
  "throughput":  100.02,
  "success":     1.0,
  "status_codes": { "200": 500 },
  "errors":      []
}
```

Key fields a parser pulls out:

- **`latencies`** — sub-object with `total`, `mean`, `50th`, `95th`,
  `99th`, `max`, `min`. **All values are in nanoseconds** (int64).
  This is vegeta's load-bearing output — the full parser target.
- **`bytes_in`** / **`bytes_out`** — each is a sub-object with
  `total` (int, bytes) and `mean` (float, bytes/request). For
  a GET benchmark `bytes_out` is typically zero.
- **`earliest`** / **`latest`** / **`end`** — RFC 3339 timestamps
  for the first request sent, the last response received, and the
  report end. These are framework wall-clock values and **must not
  go into `timestamp`** per the parser contract — stash in
  `extra_info` if desired.
- **`duration`** — the wall-clock span of the attack, in
  **nanoseconds** (from `earliest` to `latest`).
- **`wait`** — time between the last request sent and its response
  received, in **nanoseconds**.
- **`requests`** — total request count (int).
- **`rate`** — *achieved* rate in requests/sec (float). Usually
  very close to the configured `-rate` value.
- **`throughput`** — successful responses per second (float).
  Differs from `rate` when some requests fail.
- **`success`** — fraction of successful responses (float, 0.0 to
  1.0). 1.0 means all requests returned a 2xx.
- **`status_codes`** — `{string: int}` map of status code to count
  (e.g. `{"200": 500}` or `{"200": 495, "500": 5}`).
- **`errors`** — list of error strings encountered during the
  attack; empty list on a clean run.

### Recommended parser shape

Emit one Nyrkiö test-result dict with `attributes["test_name"] =
"homepage"` and the following metrics (unit conversions shown,
direction in parentheses):

| Metric name        | Source                      | Unit     | Direction          |
| ------------------ | --------------------------- | -------- | ------------------ |
| `latency_mean`     | `latencies.mean`            | `ns`     | `lower_is_better`  |
| `latency_min`      | `latencies.min`             | `ns`     | `lower_is_better`  |
| `latency_max`      | `latencies.max`             | `ns`     | `lower_is_better`  |
| `p50`              | `latencies.50th`            | `ns`     | `lower_is_better`  |
| `p95`              | `latencies.95th`            | `ns`     | `lower_is_better`  |
| `p99`              | `latencies.99th`            | `ns`     | `lower_is_better`  |
| `rate`             | `rate`                      | `ops/s`  | `higher_is_better` |
| `throughput`       | `throughput`                | `ops/s`  | `higher_is_better` |
| `success`          | `success`                   | `ratio`  | `higher_is_better` |
| `requests`         | `requests`                  | `count`  | informational      |
| `bytes_in_total`   | `bytes_in.total`            | `bytes`  | informational      |
| `bytes_out_total`  | `bytes_out.total`           | `bytes`  | informational      |

The parser may emit latency in nanoseconds as-is (vegeta's native
unit, the finest resolution) or convert to microseconds / milli-
seconds for readability — pick one and stick with it, but the unit
string in each metric must agree with the value.

Populate `extra_info` with `earliest`, `latest`, `end`,
`duration_ns`, `status_codes`, and the target URL pulled from
`targets.txt`. Leave `timestamp: 0` per the parser contract —
**do not** populate `timestamp` from vegeta's `earliest`/`end`
fields; those are wall-clock, not git-derived.

### Failure mode

If no requests succeed (nginx never came up, connection refused
everywhere), vegeta will still produce a JSON report but with
`success: 0`, an empty or 5xx-dominated `status_codes` map, and a
populated `errors` list. The parser should detect `success < 1.0`
or a non-empty `errors` array, emit the result as usual, and set
`passed: false` so downstream consumers can decide what to do.

If vegeta itself crashes before writing `results.bin`, `output.json`
will be missing or empty — the artifact upload step uses
`if-no-files-found: error` to surface that loudly.

### Relationship to the fork

The predecessor TypeScript project at
[`nyrkio/change-detection`](https://github.com/nyrkio/change-detection)
did **not** have a vegeta parser. This is a clean-slate
implementation — no fixtures to crib, no prior art to align with.
