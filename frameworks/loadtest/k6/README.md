# k6

[k6](https://k6.io/) is Grafana's open-source load-testing tool. Tests
are written in JavaScript and executed by a Go-hosted runtime (goja).
In normal use k6 drives HTTP/gRPC/WebSocket traffic at a target service
and reports latency percentiles, request rates, and error counts.

## Links

- **Sample benchmark** — [`sample-benchmark.js`](sample-benchmark.js),
  orchestrated by [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/k6.yml`](../../../.github/workflows/k6.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/k6.yml>
- **Parser** — [`src/benchzoo/parsers/k6.py`](../../../src/benchzoo/parsers/k6.py) *(not yet written — pending a real captured fixture)*
- **Parser tests** — [`tests/parsers/test_k6.py`](../../../tests/parsers/test_k6.py) *(not yet written)*

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) in k6
idiom — with one important caveat, described next.

### Synthetic, non-HTTP adaptation

k6 is a load-test runner; it is designed to hit an HTTP (or gRPC /
WebSocket) target and measure per-request latency, not to time local
`sleep` calls or arithmetic loops. Mapping the canonical four tests to
a real HTTP workload would require standing up an nginx service
container and inventing four endpoints — overkill for what we actually
need here, which is just to exercise k6's output format for parser
development.

Instead, [`sample-benchmark.js`](sample-benchmark.js) uses k6's custom
`Trend` metric API to record per-test durations directly from inside
the VU script:

```js
const benchmark1Trend = new Trend('benchmark1', true); // true = time metric (ms)
// ... inside default function:
const t0 = performance.now();
sleep(2.15);
benchmark1Trend.add(performance.now() - t0);
```

The script runs with `vus: 1, iterations: 1` — exactly one pass through
the default function — and therefore emits exactly one data point per
custom Trend. The captured output still goes through k6's normal
summary/streaming export pipeline, which is what the parser cares
about.

A future, "real k6" framework entry could spin up an nginx container
and benchmark four HTTP endpoints against it; that is a separate
concern and does not block parser work on this output format. Flagging
this explicitly so the decision is visible.

### Per-test mapping

- **Test 1** (sleep 2.15 s) — wraps `sleep(2.15)` in a
  `performance.now()` timing block and records the elapsed ms into the
  `benchmark1` Trend. This is the one test k6 can measure faithfully.
- **Test 2** (tight CPU loop) — runs `for (let i = 0; i < 1000; i++)
  sum += i`, recording elapsed ms into `benchmark2`. We use
  `performance.now()` rather than `Date.now()` because the loop body
  is sub-millisecond and `Date.now()` would report 0 ms, which defeats
  the purpose of test 2 (exercising the parser's handling of small
  durations). k6 exposes the standard `performance.now()` API with
  sub-millisecond resolution. The result is accumulated into a `sum`
  variable that is read afterward, so the JS engine (goja) cannot elide
  the loop as dead code.
- **Test 3** (write 1.4 MB to /dev/null) — **k6's JS runtime is
  sandboxed and has no filesystem write access**, so there is no way to
  write to `/dev/null` from inside a k6 script. We emulate the test by
  allocating a 1,400,000-byte `ArrayBuffer`, wrapping it in a
  `Uint8Array`, and sparsely writing one byte every 4096 bytes. The
  recorded metric therefore measures "allocate + touch 1.4 MB of
  memory", not disk I/O. The byte count is preserved (1,400,000
  exactly) so the ground-truth magnitude is the same, but the physical
  operation is different and parser developers should not expect this
  measurement to be comparable across frameworks on the I/O axis.
- **Test 4** (monthly change point) — computes
  `2.15 + ((UTC month mod 3) - 1)` in JavaScript and sleeps for that
  many seconds, recording elapsed ms into `benchmark4`. Same
  change-point structure as every other framework's test 4.

The orchestration lives in [`run.sh`](run.sh), which invokes `k6 run`
with **both** `--summary-export=summary.json` and
`--out json=output.json`, producing two output files — one
end-of-run summary, one streaming ndjson log. See *Parser notes* below.

## Running locally

```bash
act push -W .github/workflows/k6.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/k6-output/`, which will contain both
`summary.json` and `output.json`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with k6 installed locally, you can bypass `act` entirely
and just run `bash run.sh` from this directory.

## Parser notes

k6 can emit several output formats. We capture two of them:

### `summary.json` (via `--summary-export`)

This is k6's end-of-run aggregate. A top-level dict with a `metrics`
key that maps metric name to a sub-dict of aggregate statistics. Our
four custom Trends appear as keys `benchmark1`, `benchmark2`,
`benchmark3`, `benchmark4`, alongside k6's built-in metrics
(`iteration_duration`, `iterations`, `vus`, `vus_max`, `data_sent`,
`data_received`, and — for HTTP runs — `http_req_*`, `http_reqs`,
etc.; the latter will not appear here because our script makes no HTTP
requests).

For each **Trend** metric, `values` contains (keys as strings):
`avg`, `min`, `med`, `max`, `p(90)`, `p(95)` — all in milliseconds
(because we created the Trend with `isTime = true`).

For **Rate** metrics (k6 built-ins like `checks`), `values` contains
`rate`, `passes`, `fails`.

For **Counter** metrics (`iterations`, `data_sent`, `data_received`),
`values` contains `count`, `rate`.

For **Gauge** metrics (`vus`, `vus_max`), `values` contains `value`,
`min`, `max`.

Recommended parser shape: key off `metrics.benchmark1` ..
`metrics.benchmark4` as the four `test_name`s and emit `avg`, `min`,
`max`, `med`, `p(95)` as metric entries with `unit: "ms"` and
`direction: "lower_is_better"`. (`p(90)` can be included too; `avg` is
probably the most useful single value for ground-truth assertions.)
The parser should tolerate the presence of the built-in k6 metrics and
simply skip over them — they do not map to any canonical test.

### `output.json` (via `--out json=...`) — streaming ndjson

This is k6's streaming per-data-point format: **one JSON object per
line** (newline-delimited JSON). Two kinds of lines:

- `{"type": "Metric", "data": {...}, "metric": "<name>"}` — metadata
  about a metric (its type, thresholds, contains submetrics, etc.),
  emitted once per metric at script start.
- `{"type": "Point", "data": {"time": "...", "value": ..., "tags":
  {...}}, "metric": "<name>"}` — a single data point. For our script,
  each `benchmark1`..`benchmark4` Trend produces exactly one Point line
  because the VU runs exactly once.

A parser consuming the ndjson form can filter for `type == "Point"`
and `metric` starting with `benchmark`, then emit one metric entry per
point. Because the script runs once, the ndjson "aggregate" is the raw
point itself — there is nothing to average — which differs from the
usual k6 load-test case where a parser would have to bucket points
itself. That difference is a feature of the synthetic adaptation, not
a quirk of k6.

### Cross-format consistency

Both files carry the same four measurements expressed differently:
`summary.json` has one `avg` number per Trend, `output.json` has one
Point per Trend. For a single-iteration run they should agree exactly
(modulo rounding). A parser can pick either one; the fixture on disk
is the canonical record either way. Recommendation: start with
`summary.json` because its structure is simpler.

### Timestamps

k6's Point entries carry a `time` field (ISO 8601) and the summary
dict carries a `state.testRunDurationMs`. **Neither of these should be
used for the Nyrkiö `timestamp` field** — per the parser contract in
[`docs/design.md`](../../../docs/design.md#field-semantics), parsers
always set `timestamp: 0` and leave the real timestamp to the ingest
layer, which derives it from the git commit. If the parser wants to
preserve k6's wall-clock time for reference, `extra_info` is the right
place.

### Failures

This sample benchmark has no HTTP requests and no `check()` calls, so
there is nothing that can fail-but-still-produce-a-measurement in the
k6 sense. Every run should be `passed: true`. When this framework
eventually grows a real HTTP version, the parser should consult k6's
`checks` metric and set `passed: false` on the test-results dict if any
check failed.
