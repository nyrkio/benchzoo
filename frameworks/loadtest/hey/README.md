# hey

[hey](https://github.com/rakyll/hey) is Jaana Dogan's simple HTTP
load generator, written in Go. It drives a configurable number of
concurrent workers at an HTTP endpoint for a configurable number of
requests or duration and reports summary statistics, a response-time
histogram, a latency distribution, and a status-code distribution.
It is commonly shipped as a modern drop-in replacement for Apache's
`ab`, and despite being simpler than [wrk](../wrk/) is used by many
CI dashboards for its trivial installation and readable text report.

## Links

- **Sample benchmark** — a minimal static page ([`index.html`](index.html))
  served by [`nginx.conf`](nginx.conf), load-tested by [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/hey.yml`](../../../.github/workflows/hey.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/hey.yml>
- **Parser** — [`src/benchzoo/parsers/hey.py`](../../../src/benchzoo/parsers/hey.py) *(not yet written — pending a real captured fixture)*
- **Parser tests** — [`tests/parsers/test_hey.py`](../../../tests/parsers/test_hey.py) *(not yet written)*

## Sample benchmark

hey does not fit the
[canonical sample benchmark](../../../docs/sample-benchmark.md) cleanly.
The canonical suite was designed for frameworks that time arbitrary
code (a sleep, a CPU loop, an I/O write), and the four tests exist to
stress-test parsers across very different magnitudes. hey is a
fundamentally different kind of tool: a single invocation measures
one HTTP endpoint's behavior under sustained concurrent load, and the
latency numbers are emergent properties of nginx + the kernel's TCP
stack + the runner's CPU and scheduling — not a quantity under our
control. Trying to shoehorn `sleep 2.15` into an average latency is
nonsensical.

So the adaptation is explicit and honest: **one test run, not four.**
This mirrors the deviation already taken by the
[`lighthouse`](../../frontend/lighthouse/) and [`wrk`](../wrk/)
frameworks, which had the same structural mismatch.

- **Test 1** (sleep 2.15 s) — **dropped.** hey does not measure
  arbitrary sleep; it measures HTTP request latency under load. There
  is no corresponding invocation.
- **Test 2** (tight CPU loop, sub-ms) — **dropped.** HTTP request
  latencies over loopback run in the tens-to-hundreds of microseconds
  range, not sub-microsecond. There is no sub-ms metric to exercise
  in hey's output.
- **Test 3** (write 1.4 MB to /dev/null) — **dropped.** hey reports a
  per-request size and a total size, but these are emergent from the
  load test duration and nginx's response size; we don't control them
  precisely enough to assert on a 1,400,000-byte value.
- **Test 4** (monthly change point) — **dropped.** Test 4 requires
  the measured quantity to be under our control so we can produce a
  deterministic monthly step function. hey's numbers depend on the
  runner and cannot be shaped into `2.15 + ((m mod 3) - 1)`. There
  is therefore no `schedule:` trigger on this workflow: it runs on
  push/PR and manual dispatch only.

What the framework *does* run is a single hey invocation against a
single static nginx endpoint:

```
hey -z 5s -c 10 http://localhost:8080/
```

That is: 5 second duration, 10 concurrent workers. Both flags are
hey's built-in defaults; we pass them explicitly so the command line
documents the intended load rather than relying on upstream defaults
that could shift. We treat the whole run as one test with
`attributes["test_name"] = "homepage"`, and emit every headline
number hey reports — summary stats, latency distribution percentiles,
requests/sec — as separate entries in `metrics[]`.

The page itself ([`index.html`](index.html)) is deliberately small —
a few hundred lines of static HTML with inline CSS — so nginx's
sendfile path does the work and hey's response-body handling is not
the bottleneck. No external assets, no scripts, no cookies:
everything hey sees is committed in this directory.

The orchestration lives in [`run.sh`](run.sh), which:

1. Starts `nginx -p $(pwd) -c nginx.conf` in the foreground,
   backgrounded by `&`, so it uses the local directory for its pid
   file, error log, and temp directories (no `sudo`, no
   `/var/lib/nginx`).
2. `trap`s a kill on the nginx PID so it goes away on any exit.
3. Waits a moment with a `curl` loop for nginx to bind.
4. Runs `hey -z 5s -c 10 http://localhost:8080/` and redirects both
   stdout and stderr to `output.txt`.

## Running locally

```bash
act push -W .github/workflows/hey.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/hey-output/output.txt`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with `hey` and `nginx` installed locally
(`apt install hey nginx` on Ubuntu 24.04+), you can bypass `act`
entirely and just run `./run.sh` from this directory. That produces
the same `output.txt` without the GitHub Actions artifact plumbing.

## Parser notes

hey emits a single, stable text report — **no JSON, no CSV, no
machine format**. Parsing is line-oriented string matching. Unlike
wrk, which uses unit suffixes that scale with magnitude (`us`, `ms`,
`s`), **hey reports all timings in seconds natively**, as bare
floating-point numbers without unit suffixes. The parser must convert
to a canonical unit if downstream consumers want microseconds or
milliseconds.

### The hey text output

A typical run looks roughly like:

```

Summary:
  Total:        5.0012 secs
  Slowest:      0.0238 secs
  Fastest:      0.0001 secs
  Average:      0.0002 secs
  Requests/sec: 48246.8012

  Total data:   207654321 bytes
  Size/request: 862 bytes

Response time histogram:
  0.000 [1]     |
  0.002 [238102]|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
  0.005 [2819]  |
  0.007 [152]   |
  0.010 [48]    |
  0.012 [12]    |
  0.014 [3]     |
  0.017 [1]     |
  0.019 [0]     |
  0.021 [0]     |
  0.024 [1]     |


Latency distribution:
  10% in 0.0001 secs
  25% in 0.0001 secs
  50% in 0.0002 secs
  75% in 0.0002 secs
  90% in 0.0003 secs
  95% in 0.0004 secs
  99% in 0.0010 secs

Details (average, fastest, slowest):
  DNS+dialup:   0.0000 secs, 0.0001 secs, 0.0238 secs
  DNS-lookup:   0.0000 secs, 0.0000 secs, 0.0000 secs
  req write:    0.0000 secs, 0.0000 secs, 0.0009 secs
  resp wait:    0.0001 secs, 0.0001 secs, 0.0188 secs
  resp read:    0.0000 secs, 0.0000 secs, 0.0041 secs

Status code distribution:
  [200] 241139 responses
```

Key fields a parser pulls out:

- **Summary block** — `Total`, `Slowest`, `Fastest`, `Average`,
  `Requests/sec`. All timings are in seconds (the `secs` suffix is
  always literal "secs", not a scaled unit). `Requests/sec` is a
  bare float with no unit suffix.
- **Total data / Size/request** — aggregate bytes and per-request
  response body size in bytes.
- **Response time histogram** — a fixed set of buckets from the
  observed fastest to slowest, each line formatted as
  `  <bucket_upper_sec> [<count>] |<bar>`. The bucket count is
  effectively always 11 (hey hardcodes this) but the bucket
  boundaries vary run-to-run. Useful for a full histogram view; a
  parser can stash the (boundary, count) pairs in `extra_info` or
  emit them as named metrics.
- **Latency distribution** — percentiles at 10%, 25%, 50%, 75%, 90%,
  95%, 99%. Each line: `  <N>% in <seconds> secs`. This is hey's
  richest output and the primary parser target.
- **Details block** — per-stage breakdown (DNS+dialup, DNS-lookup,
  req write, resp wait, resp read), each with three numbers:
  average, fastest, slowest. Useful but framework-specific.
- **Status code distribution** — `  [<code>] <N> responses` lines.
  Essential for detecting failed runs: a run with any non-2xx status
  codes should be flagged `passed: false`.

### Recommended parser shape

Emit one Nyrkiö test-result dict with `attributes["test_name"] =
"homepage"` and the following metrics (hey's native unit is seconds;
the parser may convert to milliseconds or microseconds per downstream
preference — the table below uses seconds for fidelity to the raw
output):

| Metric name          | Source                                | Unit     | Direction          |
| -------------------- | ------------------------------------- | -------- | ------------------ |
| `latency_avg`        | Summary → Average                     | `s`      | `lower_is_better`  |
| `latency_min`        | Summary → Fastest                     | `s`      | `lower_is_better`  |
| `latency_max`        | Summary → Slowest                     | `s`      | `lower_is_better`  |
| `p10`                | Latency distribution → 10%            | `s`      | `lower_is_better`  |
| `p25`                | Latency distribution → 25%            | `s`      | `lower_is_better`  |
| `p50`                | Latency distribution → 50%            | `s`      | `lower_is_better`  |
| `p75`                | Latency distribution → 75%            | `s`      | `lower_is_better`  |
| `p90`                | Latency distribution → 90%            | `s`      | `lower_is_better`  |
| `p95`                | Latency distribution → 95%            | `s`      | `lower_is_better`  |
| `p99`                | Latency distribution → 99%            | `s`      | `lower_is_better`  |
| `requests_per_sec`   | Summary → Requests/sec                | `ops/s`  | `higher_is_better` |
| `total_requests`     | sum of status-code counts             | `count`  | `higher_is_better` |
| `total_bytes`        | Summary → Total data                  | `bytes`  | informational      |
| `size_per_request`   | Summary → Size/request                | `bytes`  | informational      |

Populate `extra_info` with the histogram buckets, the Details-block
per-stage timings, the status-code distribution, and the configured
duration/concurrency pulled from the invocation. Leave `timestamp: 0`
per the parser contract.

### Units

**All hey timings are in seconds** and printed as bare
floating-point numbers with the literal suffix ` secs`. There is no
magnitude-scaling — a 100-microsecond average shows as `0.0001 secs`,
not `100us`. This is a deliberate contrast with wrk's format, where
the parser has to detect `us`/`ms`/`s` suffixes and rescale per
field. hey is simpler to parse but loses precision below about a
microsecond because the 4-decimal-place float rounds to zero.

Byte counts are bare integers with a literal `bytes` suffix — no
`KB`/`MB` scaling in the output we need to parse, unlike wrk's
`198.12MB read`.

### Ground-truth assertions

Unlike the canonical sample benchmark's tests 1–3, hey's
measurements are **not** fixed quantities. Latency for this
particular endpoint will depend on the runner's CPU, concurrent
noise, and TCP stack timing. Parser tests for hey must therefore use
**loose** assertions — presence-of-key and plausible-range rather
than tight numeric bounds:

- Assert `results[0]["attributes"]["test_name"] == "homepage"`.
- Assert `results[0]["timestamp"] == 0`.
- Assert the set of metric names includes `latency_avg`, `p50`,
  `p99`, `requests_per_sec` (intersection, not exact equality).
- Assert each latency metric has `value > 0` and unit `"s"` (or
  whatever canonical time unit the parser settles on).
- Assert `requests_per_sec > 0`.

This is weaker than the `2.0 < mean < 2.3` check we get from tests
1–3 in other frameworks — but it still verifies the parser is
actually reading the right fields, not just producing structurally
valid garbage.

### Failure mode

hey exits non-zero if it cannot connect to the target at all
(connection refused, DNS failure); in that case there is no
meaningful report and `output.txt` will contain an error message
instead. The parser should detect the absence of a `Summary:` block,
emit a result with `passed: false`, and either empty `metrics` or a
single informational entry. A hey run that completes but reports
non-2xx entries in the `Status code distribution:` should also be
flagged `passed: false` — hey does not otherwise signal application
errors.

### Relationship to the fork

The predecessor TypeScript project at
[`nyrkio/change-detection`](https://github.com/nyrkio/change-detection)
did **not** have a hey parser. This is a clean-slate implementation
— no fixtures to crib, no prior art to align with.

## Considered but not adopted

### JSON / CSV output

hey has none. The tool emits a single text report and that is the
entire output surface; there is no `-o json` or `--format csv` flag
to capture a richer format. Users who need machine-readable load-
test output typically reach for [vegeta](https://github.com/tsenart/vegeta)
or [k6](https://k6.io/) instead. benchzoo will ship separate
frameworks for those; hey stays in the text-parsing lane.

### `-n <count>` fixed-request mode

hey also supports `-n <N>` for a fixed request count instead of the
duration-based `-z <dur>`. We use duration mode because it produces
more stable fixture runtimes in CI — a fixed request count on a
loaded runner can take anywhere from one second to twenty, while
`-z 5s` always takes five.
