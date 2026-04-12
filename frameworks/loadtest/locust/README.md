# locust

[Locust](https://locust.io) is a Python-based, distributed load-testing
framework. Users describe a scenario as Python code — a `HttpUser`
subclass with `@task`-decorated methods — and Locust spawns a
configurable number of simulated users, each picking tasks at random
and hitting the target at a configurable pace. It reports per-endpoint
request counts, failures, response-time percentiles (p50 through
p100), average content size, and aggregate throughput. Compared to
lower-level tools like wrk, Locust's value is in scenario modeling
(multi-step user flows, stateful sessions, branching task weights) at
the cost of a less efficient request loop.

## Links

- **Sample benchmark** — a minimal static page ([`index.html`](index.html))
  served by [`nginx.conf`](nginx.conf), load-tested by
  [`locustfile.py`](locustfile.py) via [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/locust.yml`](../../../.github/workflows/locust.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/locust.yml>
- **Parser (stats CSV)** — [`src/benchzoo/parsers/locust_stats_csv.py`](../../../src/benchzoo/parsers/locust_stats_csv.py) *(not yet written — pending a real captured fixture)*
- **Parser (failures CSV)** — [`src/benchzoo/parsers/locust_failures_csv.py`](../../../src/benchzoo/parsers/locust_failures_csv.py) *(not yet written)*
- **Parser (stats history CSV)** — [`src/benchzoo/parsers/locust_stats_history_csv.py`](../../../src/benchzoo/parsers/locust_stats_history_csv.py) *(not yet written)*
- **Parser tests** — [`tests/parsers/test_locust.py`](../../../tests/parsers/test_locust.py) *(not yet written)*

## Sample benchmark

Locust does not fit the
[canonical sample benchmark](../../../docs/sample-benchmark.md) cleanly.
The canonical suite was designed for frameworks that time arbitrary
code (a sleep, a CPU loop, an I/O write), and the four tests exist to
stress-test parsers across very different magnitudes. Locust is a
fundamentally different kind of tool: a single invocation measures
one (or more) HTTP endpoints' behavior under sustained concurrent
load from simulated users, and the latency numbers are emergent
properties of nginx + the kernel's TCP stack + the runner's CPU and
scheduling — not a quantity under our control. Trying to shoehorn
`sleep 2.15` into a p99 latency is nonsensical.

So the adaptation is explicit and honest: **one test run, not four.**
This mirrors the deviation already taken by the
[`lighthouse`](../../frontend/lighthouse/) and
[`wrk`](../wrk/) frameworks, which had the same structural mismatch.

- **Test 1** (sleep 2.15 s) — **dropped.** Locust does not measure
  arbitrary sleep; it measures HTTP request latency under load.
- **Test 2** (tight CPU loop, sub-ms) — **dropped.** HTTP request
  latencies over loopback run in the tens-to-hundreds of microseconds
  range, not sub-microsecond — and Locust's CSV stats are recorded
  with millisecond resolution anyway, so there is no sub-ms metric
  to exercise.
- **Test 3** (write 1.4 MB to /dev/null) — **dropped.** Locust
  reports an average content size and a requests-per-second rate,
  but these are emergent from the nginx response size and the run
  duration; we don't control them precisely enough to assert on a
  1,400,000-byte value.
- **Test 4** (monthly change point) — **dropped.** Test 4 requires
  the measured quantity to be under our control so we can produce a
  deterministic monthly step function. Locust's numbers depend on
  the runner and cannot be shaped into `2.15 + ((m mod 3) - 1)`.
  There is therefore no `schedule:` trigger on this workflow: it
  runs on push/PR and manual dispatch only.

What the framework *does* run is a single Locust invocation against
a single static nginx endpoint, via
[`locustfile.py`](locustfile.py):

```python
class HomepageUser(HttpUser):
    host = "http://localhost:8080"

    @task
    def homepage(self):
        self.client.get("/")
```

…launched in headless mode for 10 seconds with 10 simulated users:

```
locust --headless --users 10 --spawn-rate 10 --run-time 10s \
    --csv=output --only-summary -f locustfile.py
```

We treat the whole run as one test with
`attributes["test_name"] = "homepage"` (matching the `name` column
in Locust's stats CSV, which is the URL path `/` — the parser may
choose to substitute `"homepage"` for readability).

The page itself ([`index.html`](index.html)) is deliberately small —
a few hundred lines of static HTML with inline CSS — so nginx's
sendfile path does the work and Locust's response-body parsing is
not the bottleneck. No external assets, no scripts, no cookies:
everything Locust sees is committed in this directory.

The orchestration lives in [`run.sh`](run.sh), which:

1. Starts `nginx -p $(pwd) -c nginx.conf` in the foreground,
   backgrounded by `&`, so it uses the local directory for its pid
   file, error log, and temp directories (no `sudo`, no
   `/var/lib/nginx`).
2. `trap`s a kill on the nginx PID so it goes away on any exit.
3. Waits a moment with a `curl` loop for nginx to bind.
4. Runs `locust --headless ... --csv=output` with `--only-summary`
   and `tee`s the console output to `output.txt`.

## Running locally

```bash
act push -W .github/workflows/locust.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/locust-output/`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with the requirements installed locally
(`pip install -r requirements.txt`) and nginx available
(`apt install nginx`), you can bypass `act` entirely and just run
`./run.sh` from this directory. That produces the same output files
without the GitHub Actions artifact plumbing.

## Parser notes

Locust's `--csv=<prefix>` flag writes **three** CSV files in the
current directory, each with a different schema. The workflow
captures all three, so there are three parser modules rather than
one. Locust also emits a human-readable summary table to stdout,
which we `tee` to `output.txt` — it is redundant with the CSVs but
occasionally useful for cross-checking.

### `output_stats.csv`

The primary parser target. One row per endpoint under test, plus a
final **`Aggregated`** row summing across all endpoints. Columns
(in emission order):

| Column                  | Unit    | Notes                                              |
| ----------------------- | ------- | -------------------------------------------------- |
| `Type`                  | string  | HTTP method: `GET`, `POST`, …; blank on aggregate  |
| `Name`                  | string  | URL path or route name; `Aggregated` on summary    |
| `Request Count`         | count   | Total successful + failed requests in this bucket  |
| `Failure Count`         | count   | Subset of the above that errored                   |
| `Median Response Time`  | ms      | p50 latency, integer ms                            |
| `Average Response Time` | ms      | Mean latency over the run                          |
| `Min Response Time`     | ms      | Fastest single request                             |
| `Max Response Time`     | ms      | Slowest single request                             |
| `Average Content Size`  | bytes   | Mean response body size                            |
| `Requests/s`            | ops/s   | Aggregate throughput over the run                  |
| `Failures/s`            | ops/s   | Aggregate error rate over the run                  |
| `50%`                   | ms      | p50 (same value as `Median Response Time`)         |
| `66%`                   | ms      | p66                                                |
| `75%`                   | ms      | p75                                                |
| `80%`                   | ms      | p80                                                |
| `90%`                   | ms      | p90                                                |
| `95%`                   | ms      | p95                                                |
| `98%`                   | ms      | p98                                                |
| `99%`                   | ms      | p99                                                |
| `99.9%`                 | ms      | p99.9                                              |
| `99.99%`                | ms      | p99.99                                             |
| `100%`                  | ms      | Maximum (same value as `Max Response Time`)        |

All response-time columns are **milliseconds as integers** in the
CSV — Locust rounds for the CSV report, even though internally it
measures in finer resolution. `Average Content Size` is bytes.
`Requests/s` and `Failures/s` are per-second rates averaged over
the full run duration.

### `output_failures.csv`

One row per distinct failure mode, columns: `Method`, `Name`,
`Error`, `Occurrences`. In the happy path (nginx responds 200 to
every request), this file has a **header row only** — no data
rows. The parser should handle that cleanly and emit no results
rather than crashing on an empty body.

### `output_stats_history.csv`

Time series of the stats table: one row per endpoint per
~2-second interval, plus the `Aggregated` row per interval.
Columns include `Timestamp` (unix seconds), `User Count`, `Type`,
`Name`, then the same numeric columns as `output_stats.csv`. For
a 10-second `--run-time` that is roughly five snapshots per row.
Useful if a downstream consumer wants to see within-run trends
(warm-up transients, saturation); less useful for a single-point
headline metric.

### Recommended parser shape

For `output_stats.csv`, emit one Nyrkiö test-result dict per
non-aggregate row, with `attributes["test_name"]` derived from the
`Name` column, and the following metrics (direction in parentheses):

| Metric name        | Source column             | Unit     | Direction          |
| ------------------ | ------------------------- | -------- | ------------------ |
| `request_count`    | Request Count             | `count`  | `higher_is_better` |
| `failure_count`    | Failure Count             | `count`  | `lower_is_better`  |
| `median`           | Median Response Time      | `ms`     | `lower_is_better`  |
| `mean`             | Average Response Time     | `ms`     | `lower_is_better`  |
| `min`              | Min Response Time         | `ms`     | `lower_is_better`  |
| `max`              | Max Response Time         | `ms`     | `lower_is_better`  |
| `content_size`     | Average Content Size      | `bytes`  | informational      |
| `requests_per_sec` | Requests/s                | `ops/s`  | `higher_is_better` |
| `failures_per_sec` | Failures/s                | `ops/s`  | `lower_is_better`  |
| `p50` … `p100`     | 50%, 66%, …, 100%         | `ms`     | `lower_is_better`  |

The `Aggregated` row is a second test-result dict with
`attributes["test_name"] = "Aggregated"` (or similar); downstream
consumers who want only the aggregate can filter. Leave
`timestamp: 0` per the parser contract. Set `passed = False`
if `Failure Count > 0` for that row.

For `output_failures.csv`, emit one dict per failure-mode row;
on an empty file (header only) emit `[]`.

For `output_stats_history.csv`, emit one dict per interval row,
with `extra_info["interval_timestamp"]` carrying the
wall-clock unix timestamp from the CSV (as reference only —
Nyrkiö `timestamp` remains `0`).

### Ground-truth assertions

Unlike the canonical sample benchmark's tests 1–3, Locust's
measurements are **not** fixed quantities. p99 latency for this
particular endpoint depends on the runner's CPU, concurrent noise,
and TCP stack timing. Parser tests must use **loose** assertions —
presence-of-key and plausible-range rather than tight numeric
bounds:

- Assert at least one result has `attributes["test_name"]` matching
  the homepage route.
- Assert `timestamp == 0` on every result.
- Assert the metric names include `requests_per_sec`, `mean`,
  `median`, `p99`.
- Assert each latency metric has `value > 0` and `unit == "ms"`.
- Assert `requests_per_sec > 0` and `request_count > 0`.

This is weaker than the `2.0 < mean < 2.3` check we get from tests
1–3 in other frameworks — but it still verifies the parser is
actually reading the right columns, not just producing structurally
valid garbage.

### Headless-mode gotchas

A few sharp edges worth documenting for future parser work:

- **Locust ignores `--users` / `--spawn-rate` / `--run-time`
  without `--headless`.** Without the flag it starts the web UI
  and waits for a human to click Start, which hangs CI. The
  `--headless` flag is non-optional for scripted runs.
- **`--only-summary` suppresses the periodic per-interval console
  table but does not affect the CSV files.** The CSVs are written
  regardless; the flag only affects the `output.txt` we capture.
- **The `--csv` prefix is a path prefix, not a filename.** Passing
  `--csv=output` produces `output_stats.csv`, not `output.csv`.
  The three suffixes (`_stats`, `_failures`, `_stats_history`) are
  hardcoded in Locust and not configurable.
- **Header-only `output_failures.csv`** is the happy-path outcome
  and must not trip up the parser.
- **Locust uses the target URL path as the row's `Name`** by
  default; if the scenario decorates a task with
  `self.client.get("/", name="homepage")`, that name appears
  instead. Parsers should not assume any specific convention.
- **Response times are rounded to integer milliseconds in the
  CSV.** Sub-ms requests over loopback will round to `0` or `1` —
  that's a Locust emission choice, not a parser bug.

### Relationship to the fork

The predecessor TypeScript project at
[nyrkio/change-detection](https://github.com/nyrkio/change-detection)
did **not** have a Locust parser. This is a clean-slate
implementation — no fixtures to crib, no prior art to align with.
