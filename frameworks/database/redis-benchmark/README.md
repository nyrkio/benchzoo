# redis-benchmark

[redis-benchmark](https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/benchmarks/)
is Redis's built-in load generator, shipped alongside `redis-cli` in
the `redis-tools` package. A single invocation iterates over a set of
built-in command types (SET, GET, INCR, LPUSH, RPUSH, MSET, SADD,
HSET, SPOP, RPOPLPUSH, LRANGE, MSET, …) and emits one summary row per
command with throughput and a latency distribution.

## Links

- **Sample benchmark** — orchestrated by [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/redis-benchmark.yml`](../../../.github/workflows/redis-benchmark.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/redis-benchmark.yml>
- **Parser** — *not yet written*
- **Parser tests** — *not yet written*

## Sample benchmark

**Deviation from the canonical sample benchmark.** redis-benchmark is
not a "run four arbitrary workloads" tool. It does not execute
user-supplied scripts; its entire surface is "hammer a Redis server
with one of a fixed set of built-in command shapes and summarise the
latency distribution." There is no idiomatic way to express test 1's
2.15-second sleep, test 2's empty loop, test 3's 1.4 MB write to
`/dev/null`, or test 4's monthly change point as a redis-benchmark
workload.

Rather than contort the tool into shapes it doesn't support, we
**adopt the shape redis-benchmark naturally produces**: a single run
over a small, bounded subset of command types, where each command
type becomes a distinct `test_name`. The subset:

```
set, get, incr, lpush, rpush, mset
```

chosen via the `-t` flag to keep the CI run short (six commands,
100k requests each, 50 parallel clients). Other command types the
tool supports (SADD, HSET, SPOP, RPOPLPUSH, LRANGE_*, PING_INLINE,
PING_MBULK) are not invoked here — the parser does not need them to
be exercised to work on them, since every row has the same shape.

The canonical sample-benchmark's ground-truth values (2.15 s latency,
1.4 MB, month-boundary step function) do **not** apply. Parser tests
against redis-benchmark fixtures will need their own ground-truth
assertions keyed to redis-benchmark's own characteristic numbers —
for example, `GET` running on localhost with 50 clients should land
in a reasonable throughput band (tens to hundreds of thousands of
ops/s) and sub-millisecond average latency.

## Running locally

```bash
act push -W .github/workflows/redis-benchmark.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/redis-benchmark-output/` and
contains both `output.csv` and `output.txt`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with a local Redis instance running on
`localhost:6379` and `redis-tools` installed, run `./run.sh` from
this directory.

## Parser notes

Two output formats are captured per run — CSV and the default text
summary. Each gets its own parser module (not yet written; this
framework directory exists ahead of the parser).

### CSV format (`output.csv`)

`redis-benchmark --csv` in Redis 7 emits a CSV with a header row
followed by one row per command type:

```
"test","rps","avg_latency_ms","min_latency_ms","p50_latency_ms","p95_latency_ms","p99_latency_ms","max_latency_ms"
"SET","123456.78","0.321","0.048","0.295","0.551","0.799","3.215"
"GET","145678.90","0.289","0.045","0.263","0.495","0.711","2.875"
...
```

Each row maps to one Nyrkiö JSON test result with
`attributes["test_name"]` set to the command name (e.g. `"SET"`,
`"GET"`). The metrics decompose as:

- `rps` — unit `"ops/s"`, direction `"higher_is_better"`
- `avg_latency_ms`, `min_latency_ms`, `p50_latency_ms`,
  `p95_latency_ms`, `p99_latency_ms`, `max_latency_ms` — all unit
  `"ms"`, direction `"lower_is_better"`

**Gotcha — CSV header varies by Redis version.** Older Redis
releases (≤ 6.0) emitted only two columns: `"test","rps"`, with no
latency data in the CSV at all (the text output carried the
histogram). Redis 6.2 added `avg_latency_ms`. Redis 7.0 added the
min/p50/p95/p99/max columns. The parser should not hard-code column
positions; it must read the header row and key columns by name, so
that a fixture captured against an older server (or a future Redis
that adds more percentiles) still parses into a sensible
`list[dict]`. The workflow pins `redis:7`, so the captured fixture
in this repo is the 8-column shape, but parser code shouldn't
assume it.

### Text format (`output.txt`)

The default (non-CSV) output is a human-readable block per command
type, looking roughly like:

```
====== SET ======
  100000 requests completed in 0.81 seconds
  50 parallel clients
  3 bytes payload
  keep alive: 1
  host configuration "save": 3600 1 300 100 60 10000
  ...

Latency by percentile distribution:
0.000% <= 0.047 milliseconds (cumulative count 1)
50.000% <= 0.295 milliseconds (cumulative count 52431)
...
100.000% <= 3.215 milliseconds (cumulative count 100000)

Cumulative distribution of latencies:
0.000% <= 0.047 milliseconds
...

Summary:
  throughput summary: 123456.78 requests per second
  latency summary (msec):
          avg       min       p50       p95       p99       max
        0.321     0.048     0.295     0.551     0.799     3.215
```

The `====== <CMD> ======` banner is the block boundary and the source
of truth for `attributes["test_name"]`. The `Summary:` block at the
bottom of each command contains the same numbers as the CSV row;
parsers targeting the text format should generally prefer the
`Summary:` block over re-deriving values from the percentile table.

### Failure handling

redis-benchmark exits non-zero on connection failure and writes an
error message ahead of any summary. If a parser encounters a block
(or CSV row) missing its throughput or latency numbers, emit the
result with whatever it found and set `passed: false`, per the
"record but do not filter" rule in
[`docs/design.md`](../../../docs/design.md#library-boundaries).

### Relationship to the fork

The predecessor TypeScript project at `nyrkio/change-detection` did
not ship a redis-benchmark parser. This is a clean-slate parser
with no prior fixtures or design decisions to preserve.
