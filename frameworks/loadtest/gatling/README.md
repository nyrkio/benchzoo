# gatling

[Gatling](https://gatling.io/) is a Scala-based load-testing tool
popular for serious HTTP and protocol-level load tests. It runs
user-defined *simulations* — scenarios plus an injection profile —
and produces both a machine-readable event log (`simulation.log`) and
a rich HTML report with response-time distributions, percentile
curves, and per-request breakdowns. Modern Gatling (3.10+) ships a
first-class Java DSL, so writing simulations no longer requires a
Scala toolchain.

## Links

- **Sample benchmark** — a minimal static page ([`index.html`](index.html))
  served by [`nginx.conf`](nginx.conf), load-tested by a Java Gatling
  simulation ([`src/main/java/sample/BenchSimulation.java`](src/main/java/sample/BenchSimulation.java))
  wired up via Maven ([`pom.xml`](pom.xml)) and orchestrated by
  [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/gatling.yml`](../../../.github/workflows/gatling.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/gatling.yml>
- **Parser** — [`src/benchzoo/parsers/gatling.py`](../../../src/benchzoo/parsers/gatling.py) *(not yet written — pending a real captured fixture)*
- **Parser tests** — [`tests/parsers/test_gatling.py`](../../../tests/parsers/test_gatling.py) *(not yet written)*

## Sample benchmark

Gatling does not fit the
[canonical sample benchmark](../../../docs/sample-benchmark.md) cleanly.
The canonical suite was designed for frameworks that time arbitrary
code (a sleep, a CPU loop, an I/O write). Gatling is a fundamentally
different kind of tool: a simulation drives concurrent virtual users
at an HTTP endpoint and the latency numbers are emergent properties
of nginx + the kernel's TCP stack + the runner's CPU and scheduling —
not a quantity under our control. Trying to shoehorn `sleep 2.15`
into a p99 latency is nonsensical.

So the adaptation is explicit and honest: **one simulation, not
four.** This mirrors the deviation already taken by the
[`wrk`](../wrk/) and [`lighthouse`](../../frontend/lighthouse/)
frameworks.

- **Test 1** (sleep 2.15 s) — **dropped.** Gatling does not measure
  arbitrary sleep; it measures HTTP request latency under load.
- **Test 2** (tight CPU loop, sub-ms) — **dropped.** HTTP request
  latencies over loopback run in the tens-to-hundreds of microseconds
  range; Gatling's event log records milliseconds.
- **Test 3** (write 1.4 MB to /dev/null) — **dropped.** Response
  bytes are emergent from the load test duration and nginx's
  response size; we don't control them precisely enough to assert on
  a 1,400,000-byte value.
- **Test 4** (monthly change point) — **dropped.** Gatling's numbers
  depend on the runner and cannot be shaped into
  `2.15 + ((m mod 3) - 1)`. No `schedule:` trigger on this workflow.

What the framework *does* run is a single Gatling simulation against
a single static nginx endpoint. The simulation
([`BenchSimulation.java`](src/main/java/sample/BenchSimulation.java))
is a ~20-line Java file:

- an `HttpProtocolBuilder` with `baseUrl("http://localhost:8080")`,
- one scenario named `"homepage"` doing `http("get /").get("/")`,
- an open-model injection profile:
  `constantUsersPerSec(10).during(Duration.ofSeconds(5))` — i.e. a
  steady 10 new virtual users per second for 5 seconds, each firing
  a single GET. That is ~50 total requests, enough to populate a
  latency distribution without spending significant CI time.

We treat the whole run as one test with
`attributes["test_name"] = "homepage"`, and emit aggregate latency
statistics across all REQUEST events — mean, p50, p95, p99, max,
plus request count and success rate — as separate entries in
`metrics[]`.

The page itself ([`index.html`](index.html)) is deliberately small
— a few paragraphs of inline-styled HTML — so nginx's sendfile path
does the work and response parsing is not the bottleneck. No
external assets, no scripts, no cookies.

The orchestration lives in [`run.sh`](run.sh), which:

1. Starts `nginx -p $(pwd) -c nginx.conf` in the foreground,
   backgrounded by `&`, with its pid file and temp dirs under the
   local directory (no `sudo`, no `/var/lib/nginx`).
2. `trap`s a kill on the nginx PID so it goes away on any exit.
3. Waits with a `curl` loop for nginx to bind.
4. Runs `mvn -q gatling:test -Dgatling.simulationClass=sample.BenchSimulation`.
5. Copies the resulting `target/gatling/<timestamp>/simulation.log`
   to `./output.log`.

## Why Java DSL + Maven rather than Scala + sbt

Gatling's original DSL was Scala-only, and many existing tutorials
assume an sbt toolchain. Gatling 3.10+ added a first-class Java DSL
that's strictly equivalent — same classes, same behavior, same
output format — so a simulation can be written in plain Java 17 and
built with Maven.

We pick Java + Maven because:

- GitHub's hosted `ubuntu-latest` runners already have Maven;
  `actions/setup-java` provides the JDK with Maven cache support
  out of the box.
- Bootstrapping Scala on CI means installing sbt, resolving the
  Scala compiler, and dealing with sbt's own cache layout — a much
  bigger install for no improvement in the captured output.
- Most readers of this repo will find Java clearer than Scala.

The captured `simulation.log` is identical regardless of which DSL
wrote the simulation; the parser does not care.

## Running locally

```bash
act push -W .github/workflows/gatling.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/gatling-output/output.log`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with `mvn` (Maven 3.8+), JDK 17, and `nginx` installed
locally (`apt install maven openjdk-17-jdk nginx`), you can bypass
`act` entirely and just run `./run.sh` from this directory. The
first invocation downloads Gatling and its transitive dependencies
into `~/.m2/repository/` — expect a one-time ~30–60 second
download. Subsequent runs are fast.

## Parser notes

Gatling's primary machine-readable output is `simulation.log`, a
tab-separated text file that records every event the simulation
emitted. It is Gatling's own format — not CSV, not JSON — and is
designed to be re-read by Gatling itself when generating the HTML
report from a prior run (`gatling-maven-plugin:report`). It is also
the only stable, parseable representation of the raw per-request
data; the HTML report is pretty but not parseable.

### The simulation.log format

Each line is a tab-separated record whose first field is a type
marker. The relevant types are:

- **`RUN`** — one line per run, at the top. Carries the simulation
  class name, a run description, the Gatling version, and the start
  timestamp.
- **`USER`** — one line each for virtual-user start and end events.
  Not useful for the parser except as a sanity check that the
  expected number of users actually ran.
- **`REQUEST`** — **the interesting lines.** One line per HTTP
  request, with tab-separated fields:

  ```
  REQUEST \t <scenario> \t <user_id> \t <request_name> \t <start_ts> \t <end_ts> \t <status> \t [error_message]
  ```

  - `scenario` — the scenario name (`"homepage"` in our case).
  - `user_id` — the virtual-user id (integer).
  - `request_name` — the label passed to `http(...)` (`"get /"`).
  - `start_ts` / `end_ts` — epoch **milliseconds** (not seconds,
    not microseconds).
  - `status` — `OK` or `KO` (Gatling's convention for
    success/failure).
  - `error_message` — present only on `KO` lines.

  Latency per request is `end_ts - start_ts` in milliseconds.

Gatling has adjusted this format across versions (field counts and
order have shifted between 3.x minor versions). The parser should
be tolerant of extra trailing fields and should key on the `REQUEST`
marker being at column 0 and on field positions rather than on a
fixed field count.

### Recommended parser shape

Emit one Nyrkiö test-result dict with
`attributes["test_name"] = "homepage"` and metrics computed by
aggregating across all `REQUEST` rows:

| Metric name       | Source                              | Unit    | Direction          |
| ----------------- | ----------------------------------- | ------- | ------------------ |
| `latency_mean`    | mean of (end_ts − start_ts)         | `ms`    | `lower_is_better`  |
| `p50`             | 50th percentile of latencies        | `ms`    | `lower_is_better`  |
| `p95`             | 95th percentile of latencies        | `ms`    | `lower_is_better`  |
| `p99`             | 99th percentile of latencies        | `ms`    | `lower_is_better`  |
| `latency_max`     | max latency                         | `ms`    | `lower_is_better`  |
| `total_requests`  | count of REQUEST rows               | `count` | `higher_is_better` |
| `success_rate`    | OK rows / total rows                | `ratio` | `higher_is_better` |

Populate `extra_info` with the Gatling version from the `RUN` line,
the scenario name, and the injection profile summary if available.
Leave `timestamp: 0` per the parser contract.

### Ground-truth assertions

Like `wrk`, Gatling's measurements are **not** fixed quantities.
Latencies depend on the runner's CPU, concurrent noise, and TCP
stack timing. Parser tests must therefore use **loose** assertions:

- Assert `results[0]["attributes"]["test_name"] == "homepage"`.
- Assert `results[0]["timestamp"] == 0`.
- Assert the metric names include `latency_mean`, `p50`, `p99`,
  `total_requests`, `success_rate`.
- Assert each latency metric has `value > 0` and `unit == "ms"`.
- Assert `total_requests > 0` (the 5-second injection should yield
  on the order of 50 requests).
- Assert `success_rate == 1.0` under normal conditions (loopback
  nginx shouldn't drop anything).

### Failure mode

If nginx isn't up when Gatling starts, REQUEST rows will have
`status = KO` and an error message in the trailing field. The
parser should record those as usual, compute `success_rate` from
the mix, and set `passed: false` if `success_rate < 1.0`.

If `simulation.log` contains no REQUEST rows at all (the Maven build
failed, or Gatling exited before any user ran), the parser should
emit a single result with empty `metrics`, `passed: false`, and an
`extra_info["error"]` noting the absence.

### Relationship to the fork

The predecessor TypeScript project at
[`nyrkio/change-detection`](https://github.com/nyrkio/change-detection)
did **not** have a Gatling parser. This is a clean-slate
implementation — no fixtures to crib, no prior art to align with.
