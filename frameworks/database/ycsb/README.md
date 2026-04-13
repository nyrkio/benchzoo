# ycsb

[YCSB](https://github.com/brianfrankcooper/YCSB) (Yahoo Cloud Serving
Benchmark) is the de-facto standard for comparing NoSQL and
distributed-database throughput and latency. It ships a Java core
that drives a pluggable binding per target database (Cassandra,
MongoDB, Redis, DynamoDB, HBase, …); the workload shape — record
count, operation mix, key distribution — is declared in a text
properties file shared across all bindings.

We run YCSB against **Redis** via the
`ycsb-redis-binding-0.17.0.tar.gz` release tarball, because the Redis
service container is trivial to stand up (we already use it for
[redis-benchmark](../redis-benchmark/)). The choice of database is
incidental — the output format is the same regardless of binding.

## Links

- **Sample benchmark** — orchestrated by [`run.sh`](run.sh), with the
  workload defined in [`workload.txt`](workload.txt)
- **Workflow** — [`.github/workflows/ycsb.yml`](../../../.github/workflows/ycsb.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/ycsb.yml>
- **Parser** — *not yet written*
- **Parser tests** — *not yet written*

## Sample benchmark

**Deviation from the canonical sample benchmark.** YCSB is a
database workload generator, not a runner for arbitrary scripts. Its
entire surface is "pre-load N rows, then issue M read/update/insert
/scan operations against them under a chosen key distribution." A
2.15-second sleep, an empty CPU loop, a 1.4 MB write to `/dev/null`,
or a monthly step-function sleep cannot be expressed as a YCSB
workload.

Rather than contort YCSB into a shape it doesn't support, we adopt
the shape it naturally produces: one run of the classic **Workload
A** (50/50 read/update, zipfian distribution), with YCSB's three
per-phase operation types — `INSERT` (load phase), `READ` (run
phase), `UPDATE` (run phase) — each becoming a distinct `test_name`.

Parameters pinned in [`workload.txt`](workload.txt):

| key                   | value     |
| --------------------- | --------- |
| `recordcount`         | `1000`    |
| `operationcount`      | `10000`   |
| `readproportion`      | `0.5`     |
| `updateproportion`    | `0.5`     |
| `requestdistribution` | `zipfian` |

Small counts keep the CI run bounded; the parser's job is the same
whether YCSB processed a thousand ops or a billion.

The canonical sample-benchmark's ground-truth values (2.15 s, 1.4 MB,
month-boundary step function) do **not** apply. Parser tests against
YCSB fixtures will need their own ground-truth assertions keyed to
YCSB's own characteristic numbers — e.g. `READ` on localhost Redis
should land in a reasonable throughput band (tens of thousands of
ops/s) and sub-millisecond average latency.

## Running locally

```bash
act push -W .github/workflows/ycsb.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/ycsb-output/` and contains both
`output-load.txt` and `output-run.txt`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with a local Redis instance running on
`localhost:6379`, Java 11+ installed, and the
`ycsb-redis-binding-0.17.0.tar.gz` tarball extracted into this
directory (so `./ycsb-0.17.0/bin/ycsb` exists), run `./run.sh` from
here.

## Parser notes

YCSB emits one output format — a plain-text summary block printed to
stdout at the end of each phase. There is no JSON or CSV flag in
upstream 0.17.0. We therefore capture two text files — one per phase
— in the single `ycsb-output` artifact.

### Text format (`output-load.txt`, `output-run.txt`)

Each phase ends with a summary block consisting of a series of lines
of the shape:

```
[OVERALL], RunTime(ms), 5023
[OVERALL], Throughput(ops/sec), 1990.84
[READ], Operations, 5000
[READ], AverageLatency(us), 43.2
[READ], MinLatency(us), 12
[READ], MaxLatency(us), 1523
[READ], 95thPercentileLatency(us), 180
[READ], 99thPercentileLatency(us), 412
[READ], Return=OK, 5000
[UPDATE], Operations, 5000
[UPDATE], AverageLatency(us), 51.7
[UPDATE], MinLatency(us), 14
[UPDATE], MaxLatency(us), 2011
[UPDATE], 95thPercentileLatency(us), 210
[UPDATE], 99thPercentileLatency(us), 498
[UPDATE], Return=OK, 5000
```

The load phase's output looks the same but uses an `[INSERT]` section
instead of `[READ]` / `[UPDATE]`:

```
[OVERALL], RunTime(ms), 812
[OVERALL], Throughput(ops/sec), 1231.53
[INSERT], Operations, 1000
[INSERT], AverageLatency(us), 38.9
...
```

### Shape the parser produces

Split the summary lines by the bracketed section tag. The section
tag (minus the brackets, lowercased) becomes
`attributes["test_name"]` — i.e. `"read"`, `"update"`, `"insert"`.
The `[OVERALL]` section applies to the whole phase and is typically
either attached to every per-op test result as extra context or
emitted as its own `test_name: "overall"` result.

Per operation type, the parser emits these metrics:

| line                             | metric name             | unit      | direction          |
| -------------------------------- | ----------------------- | --------- | ------------------ |
| `AverageLatency(us)`             | `avg_latency`           | `"us"`    | `lower_is_better`  |
| `MinLatency(us)`                 | `min_latency`           | `"us"`    | `lower_is_better`  |
| `MaxLatency(us)`                 | `max_latency`           | `"us"`    | `lower_is_better`  |
| `95thPercentileLatency(us)`      | `p95`                   | `"us"`    | `lower_is_better`  |
| `99thPercentileLatency(us)`      | `p99`                   | `"us"`    | `lower_is_better`  |
| `[OVERALL] RunTime(ms)`          | `runtime`               | `"ms"`    | `lower_is_better`  |
| `[OVERALL] Throughput(ops/sec)`  | `throughput`            | `"ops/s"` | `higher_is_better` |

**Units gotcha — microseconds, not milliseconds.** YCSB's latency
columns are labelled `(us)` in the text output and the value is
indeed microseconds. A parser that blindly copies the number and
labels it `"ms"` will be wrong by a factor of 1000. Read the unit
from the parenthesised suffix in the line; don't hard-code it.
`RunTime` is in `ms`; `Throughput` is ops per second.

**Regex shape.** A single regex captures every summary line:

```
^\[(?P<section>[^\]]+)\],\s*(?P<metric>[^,]+?)(?:\((?P<unit>[^)]+)\))?,\s*(?P<value>[-+0-9.eE]+)\s*$
```

The unit group is optional because some lines (`Operations`,
`Return=OK`, `Return=NOT_FOUND`) carry no unit. Lines like
`Return=OK, 5000` are operation-count bookkeeping, not metrics;
the parser can either skip them or surface them in `extra_info`.

### Failure handling

YCSB emits `Return=ERROR` or `Return=NOT_FOUND` counts for a section
when operations failed. Per the "record but do not filter" rule in
[`docs/design.md`](../../../docs/design.md#library-boundaries), a
parser seeing any non-OK return count on a section should still emit
the section's latency/throughput metrics and set `passed: false` on
that test-result dict.

### Phase identification

Because load and run phases are captured as separate files with the
same summary shape, the parser cannot tell them apart from line
content alone. The intended convention is that the consumer passes
one file's bytes at a time and supplies the phase via
`extra_info["phase"]` — or that the parser is called twice, once
per file, with the phase stashed by the caller. Within a single
file, the section tag (`[INSERT]` vs `[READ]`/`[UPDATE]`) already
disambiguates per-op identity.

### Relationship to the fork

The predecessor TypeScript project at `nyrkio/change-detection` did
not ship a YCSB parser. This is a clean-slate parser with no prior
fixtures or design decisions to preserve.
