# memtier_benchmark

[memtier_benchmark](https://github.com/RedisLabs/memtier_benchmark) is
Redis Labs' load generator for Redis and memcached. A single
invocation drives a configurable mix of SET / GET (and, for memcached,
other) operations against the server and reports per-operation-type
throughput and latency statistics plus an overall latency histogram.
It is richer than `redis-benchmark`: it exposes separate SET vs. GET
breakdowns, hit/miss counters, a full percentile table per operation
type, and bandwidth numbers — and it can emit structured JSON
alongside the pretty text table.

## Links

- **Sample benchmark** — orchestrated by [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/memtier.yml`](../../../.github/workflows/memtier.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/memtier.yml>
- **Parser** — *not yet written*
- **Parser tests** — *not yet written*

## Sample benchmark

**Deviation from the canonical sample benchmark.** Like
[redis-benchmark](../redis-benchmark/README.md), memtier_benchmark is
not a "run four arbitrary workloads" tool. It does not execute
user-supplied scripts; its entire surface is "hammer a Redis or
memcached server with a configured mix of SET/GET operations and
summarise the latency distribution." There is no idiomatic way to
express test 1's 2.15-second sleep, test 2's empty loop, test 3's
1.4 MB write to `/dev/null`, or test 4's monthly change point as a
memtier workload.

Rather than contort the tool, we **adopt the shape memtier naturally
produces**: a single run with a fixed configuration, where each
operation-type row in the output becomes a distinct `test_name`. The
configuration:

```
--protocol redis --test-time=5 --ratio=1:1 --data-size=64
--clients=10 --threads=2 --pipeline=1
```

runs a 5-second 50/50 SET/GET mix with 20 total clients (10 × 2
threads) and no pipelining, against the Redis 7 service container.

The canonical sample-benchmark's ground-truth values (2.15 s latency,
1.4 MB, month-boundary step function) do **not** apply. Parser tests
against memtier fixtures will need their own ground-truth assertions
keyed to memtier's own characteristic numbers — for example, `Sets`
and `Gets` on localhost Redis with 20 clients should land in a
reasonable throughput band (tens to hundreds of thousands of ops/s)
and sub-millisecond average latency.

## Running locally

```bash
act push -W .github/workflows/memtier.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/memtier-output/` and contains both
`output.json` and `output.txt`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with a local Redis instance running on
`localhost:6379` and `memtier_benchmark` installed, run `./run.sh`
from this directory.

## Parser notes

Two output formats are captured per run — JSON (from
`--json-out-file`) and the default human-readable text table
(captured from stdout via `tee`). Each gets its own parser module
(not yet written; this framework directory exists ahead of the
parser).

### JSON format (`output.json`)

memtier's `--json-out-file` emits a single JSON document with
roughly this top-level shape:

```json
{
  "Runtime": {
    "Start time": "...",
    "Finish time": "...",
    "Total duration": 5.01,
    ...
  },
  "ALL STATS": {
    "Sets": {
      "Ops/sec":   45678.90,
      "Hits/sec":  0.00,
      "Misses/sec":0.00,
      "Latency":   { "Average": 0.321, "Min": 0.048, "Max": 3.215,
                     "p50": 0.295, "p90": 0.499, "p95": 0.551,
                     "p99": 0.799, "p99.9": 1.234 },
      "KB/sec":    5432.10
    },
    "Gets": {
      "Ops/sec":   45123.45,
      "Hits/sec":  22000.00,
      "Misses/sec":23123.45,
      "Latency":   { ... same shape ... },
      "KB/sec":    1234.56
    },
    "Totals": {
      "Ops/sec":   90802.35,
      "Hits/sec":  22000.00,
      "Misses/sec":23123.45,
      "Latency":   { ... same shape ... },
      "KB/sec":    6666.66
    }
  }
}
```

Each of the three operation-type blocks under `ALL STATS` (`Sets`,
`Gets`, `Totals`) maps to one Nyrkiö JSON test result with
`attributes["test_name"]` set to the operation type lowercased
(`"sets"`, `"gets"`, `"totals"`). The metrics decompose as:

- `Ops/sec` → name `"ops_per_sec"`, unit `"ops/s"`, direction
  `"higher_is_better"`
- `Hits/sec`, `Misses/sec` → names `"hits_per_sec"`,
  `"misses_per_sec"`, unit `"ops/s"` (direction omitted — "higher
  hits is better" but "higher misses is worse" and the mapping
  depends on workload intent, so leave it out)
- `Latency.Average`, `Min`, `Max`, `p50`, `p90`, `p95`, `p99`,
  `p99.9` → names `"latency_avg"`, `"latency_min"`, `"latency_max"`,
  `"p50"`, `"p90"`, `"p95"`, `"p99"`, `"p99_9"`, unit `"ms"`,
  direction `"lower_is_better"`
- `KB/sec` → name `"kb_per_sec"`, unit `"KB/s"`, direction
  `"higher_is_better"`

The `Runtime` block (start/finish times, total duration) is metadata
— stash the total duration in `extra_info` if useful, but do not
treat the start/finish timestamps as the Nyrkiö `timestamp` field
(see [design.md](../../../docs/design.md) on the git-derived
`timestamp` semantics — parsers always set `timestamp: 0`).

### Text format (`output.txt`)

The default (non-JSON) output is a pretty table with a banner per
operation type followed by a percentile row and finally a combined
summary, looking roughly like:

```
[RUN #1 100%, ...] ...

ALL STATS
=========================================================================
Type         Ops/sec     Hits/sec   Misses/sec   Avg. Latency   p50 Latency   ...  KB/sec
-------------------------------------------------------------------------
Sets        45678.90         ---          ---         0.32100       0.29500   ...  5432.10
Gets        45123.45    22000.00     23123.45         0.31800       0.29100   ...  1234.56
Totals      90802.35    22000.00     23123.45         0.31950       0.29300   ...  6666.66
```

The same data as the JSON — the parser should prefer the JSON as
the source of truth and treat the text parser as a secondary format
for users who only have the stdout capture. Column widths vary by
version; a text parser should key columns by header name, not by
byte offset.

### Failure handling

memtier exits non-zero on connection failure and writes an error
message to stderr (which `run.sh` folds into `output.txt` via
`2>&1`). If a parser encounters a result block missing its
throughput or latency numbers, emit the result with whatever it
found and set `passed: false`, per the "record but do not filter"
rule in
[`docs/design.md`](../../../docs/design.md#library-boundaries).

### Relationship to the fork

The predecessor TypeScript project at `nyrkio/change-detection` did
not ship a memtier_benchmark parser. This is a clean-slate parser
with no prior fixtures or design decisions to preserve.
