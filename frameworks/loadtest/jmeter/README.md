# jmeter

[Apache JMeter](https://jmeter.apache.org/) is the old-guard
enterprise HTTP load testing tool — a Java Swing application that
drives configurable thread groups at an HTTP endpoint (among many
other protocols) and emits a per-sample results log in CSV or XML.
It has been ubiquitous in enterprise performance testing for two
decades and shows no sign of going away. Its per-sample CSV output
is the easier ingest path; XML (JTL) carries the same information
with more ceremony.

## Links

- **Sample benchmark** — a minimal static page ([`index.html`](index.html))
  served by [`nginx.conf`](nginx.conf), load-tested by a small
  [`test-plan.jmx`](test-plan.jmx) invoked from [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/jmeter.yml`](../../../.github/workflows/jmeter.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/jmeter.yml>
- **Parser** — [`src/benchzoo/parsers/jmeter.py`](../../../src/benchzoo/parsers/jmeter.py) *(not yet written — pending a real captured fixture)*
- **Parser tests** — [`tests/parsers/test_jmeter.py`](../../../tests/parsers/test_jmeter.py) *(not yet written)*

## Sample benchmark

JMeter does not fit the
[canonical sample benchmark](../../../docs/sample-benchmark.md) cleanly.
The canonical suite was designed for frameworks that time arbitrary
code (a sleep, a CPU loop, an I/O write), and the four tests exist to
stress-test parsers across very different magnitudes. JMeter is a
fundamentally different kind of tool: a single test plan invocation
measures one or more HTTP endpoints under sustained concurrent load,
and the latency numbers are emergent properties of nginx + the
kernel's TCP stack + the runner's CPU and scheduling — not a quantity
under our control. Trying to shoehorn `sleep 2.15` into a p99 latency
is nonsensical.

So the adaptation is explicit and honest: **one test run, not four.**
This mirrors the deviation already taken by the
[`wrk`](../wrk/) and [`lighthouse`](../../frontend/lighthouse/)
frameworks, which had the same structural mismatch.

- **Test 1** (sleep 2.15 s) — **dropped.** JMeter does not measure
  arbitrary sleep; it measures HTTP request latency under load.
- **Test 2** (tight CPU loop, sub-ms) — **dropped.** HTTP request
  latencies over loopback run in the tens-to-hundreds of microseconds
  range; JMeter's CSV timer resolution is in milliseconds, coarser
  than what the canonical sub-ms test exercises anyway.
- **Test 3** (write 1.4 MB to /dev/null) — **dropped.** JMeter
  reports per-sample byte counts but they are emergent from nginx's
  response size; we don't control them precisely enough to assert on
  a 1,400,000-byte value.
- **Test 4** (monthly change point) — **dropped.** Test 4 requires
  the measured quantity to be under our control so we can produce a
  deterministic monthly step function. JMeter's numbers depend on
  the runner and cannot be shaped into `2.15 + ((m mod 3) - 1)`.
  There is therefore no `schedule:` trigger on this workflow: it
  runs on push/PR and manual dispatch only.

What the framework *does* run is a single JMeter test plan against a
single static nginx endpoint:

```
jmeter -n -t test-plan.jmx -l output.csv -j jmeter.log
```

The [`test-plan.jmx`](test-plan.jmx) defines one ThreadGroup with
10 threads and 100 loops (1000 total requests) pointing at
`http://localhost:8080/`, and one HTTP Sampler labelled `homepage`
with explicit connect (5 s) and response (10 s) timeouts. `-n` is
non-GUI ("command-line") mode, `-l` writes the per-sample CSV
results file, `-j` captures JMeter's own run log separately.

We treat the whole run as one test with
`attributes["test_name"] = "homepage"` (matching the sampler label)
and emit aggregated percentile metrics computed by the parser from
the per-row CSV.

The page itself ([`index.html`](index.html)) is deliberately small
— a few hundred lines of static HTML with inline CSS — so nginx's
sendfile path does the work and JMeter's response-body parsing is
not the bottleneck. No external assets, no scripts, no cookies:
everything JMeter sees is committed in this directory.

The orchestration lives in [`run.sh`](run.sh), which:

1. Starts `nginx -p $(pwd) -c nginx.conf` in the foreground,
   backgrounded by `&`, so it uses the local directory for its pid
   file, error log, and temp directories (no `sudo`, no
   `/var/lib/nginx`).
2. `trap`s a kill on the nginx PID so it goes away on any exit.
3. Waits a moment with a `curl` loop for nginx to bind.
4. Runs `jmeter -n -t test-plan.jmx -l output.csv -j jmeter.log`.

## Running locally

```bash
act push -W .github/workflows/jmeter.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/jmeter-output/` and contains
both `output.csv` (per-sample results) and `jmeter.log` (run log).
See [`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with `jmeter` and `nginx` installed locally
(`apt install jmeter nginx`), you can bypass `act` entirely and
just run `./run.sh` from this directory.

## Parser notes

*Parser not yet written.* The notes below describe the shape the
parser should implement.

### The JMeter CSV output

JMeter's default CSV output (when `-l output.csv` is passed and the
`jmeter.save.saveservice.output_format=csv` property is in effect,
which is the stock default) has this header:

```
timeStamp,elapsed,label,responseCode,responseMessage,threadName,dataType,success,failureMessage,bytes,sentBytes,grpThreads,allThreads,URL,Latency,IdleTime,Connect
```

Field meanings:

| Column            | Meaning                                                            |
| ----------------- | ------------------------------------------------------------------ |
| `timeStamp`       | Start time of the sample, Unix epoch **milliseconds** (not seconds) |
| `elapsed`         | Total sample time in **milliseconds** (end − start)                |
| `label`           | Sampler name — `"homepage"` for us                                 |
| `responseCode`    | HTTP status, e.g. `200`                                            |
| `responseMessage` | HTTP reason phrase, e.g. `OK`                                      |
| `threadName`      | `"<ThreadGroupName> 1-3"` style                                    |
| `dataType`        | `text`, `bin`, …                                                   |
| `success`         | `true` / `false` — JMeter's assertion-level pass/fail              |
| `failureMessage`  | Empty unless an assertion failed                                   |
| `bytes`           | Response body bytes                                                |
| `sentBytes`       | Request bytes sent                                                 |
| `grpThreads`      | Active threads in this thread group at sample time                 |
| `allThreads`      | Active threads across the whole test                               |
| `URL`             | Full request URL                                                   |
| `Latency`         | Time to first byte, **milliseconds**                               |
| `IdleTime`        | Idle time subtracted from elapsed, **milliseconds**                |
| `Connect`         | TCP connect time, **milliseconds**                                 |

**All times are in milliseconds.** Unlike wrk (which emits
pre-aggregated percentiles in its text report), JMeter's CSV is
raw: **one row per request, not aggregate stats.** Our test plan
(10 threads × 100 loops) produces 1,000 rows.

### Recommended parser shape

The parser groups rows by `label` and aggregates each group into a
single Nyrkiö test-result dict. For our test plan that yields one
dict with `attributes["test_name"] = "homepage"` (the sampler
label) and the following metrics:

| Metric name          | Source (aggregated across rows)        | Unit     | Direction          |
| -------------------- | -------------------------------------- | -------- | ------------------ |
| `elapsed_mean`       | mean of `elapsed` column               | `ms`     | `lower_is_better`  |
| `elapsed_p50`        | p50 of `elapsed` column                | `ms`     | `lower_is_better`  |
| `elapsed_p95`        | p95 of `elapsed` column                | `ms`     | `lower_is_better`  |
| `elapsed_p99`        | p99 of `elapsed` column                | `ms`     | `lower_is_better`  |
| `elapsed_max`        | max of `elapsed` column                | `ms`     | `lower_is_better`  |
| `latency_mean`       | mean of `Latency` column               | `ms`     | `lower_is_better`  |
| `latency_p95`        | p95 of `Latency` column                | `ms`     | `lower_is_better`  |
| `connect_mean`       | mean of `Connect` column               | `ms`     | `lower_is_better`  |
| `total_requests`     | row count for the label                | `count`  | `higher_is_better` |
| `error_count`        | count of rows with `success=false`     | `count`  | `lower_is_better`  |
| `error_rate`         | `error_count / total_requests`         | `ratio`  | `lower_is_better`  |

Populate `extra_info` with `url` (from any row's `URL` column —
should be identical across rows for a given label), the test plan
file name, and JMeter's reported thread count. Leave `timestamp: 0`
per the parser contract — **do not** use the CSV's `timeStamp`
column for the top-level `timestamp` (that is the sample's
wall-clock start, not a git commit time; the parser contract
reserves `timestamp` for the ingest-layer-injected commit time).
If you want to preserve the run start, stash it in
`extra_info["start_time_ms"]`.

If any row has `success=false`, set `passed: false` on the
aggregated dict. The library's rule is "record, don't filter" — the
failed rows still contribute to the aggregates.

### Ground-truth assertions

Unlike the canonical sample benchmark's tests 1–3, JMeter's
measurements are **not** fixed quantities. p99 latency for this
particular endpoint depends on the runner's CPU, concurrent noise,
and TCP stack timing. Parser tests for JMeter must therefore use
**loose** assertions — presence-of-key and plausible-range rather
than tight numeric bounds:

- Assert `results[0]["attributes"]["test_name"] == "homepage"`.
- Assert `results[0]["timestamp"] == 0`.
- Assert the set of metric names includes `elapsed_mean`,
  `elapsed_p95`, `elapsed_p99`, `total_requests`.
- Assert each latency metric has `value > 0` and unit `"ms"`.
- Assert `total_requests == 1000` (10 threads × 100 loops is under
  our control; unlike wrk's duration-driven request count, this one
  is deterministic).

### Failure mode

If nginx fails to bind or the test plan is malformed, JMeter may
produce an empty CSV (header only) or omit the file entirely. A
CSV with only a header row should yield either an empty `list[]`
return or a single result with `passed: false` and empty metrics —
either is acceptable; document the choice in the parser
docstring. The companion `jmeter.log` carries JMeter's own
diagnostics and is included in the artifact for post-mortem.

### XML (JTL) output

JMeter can also emit results as XML (`-l output.jtl` with
`jmeter.save.saveservice.output_format=xml`). The information
content is the same as CSV; we ship only the CSV variant for now.
If downstream demand for XML shows up, a sibling `jmeter_xml`
parser can read the same file shape via `xml.etree`.

### Relationship to the fork

The predecessor TypeScript project at
[`nyrkio/change-detection`](https://github.com/nyrkio/change-detection)
did **not** have a JMeter parser. This is a clean-slate
implementation — no fixtures to crib, no prior art to align with.
