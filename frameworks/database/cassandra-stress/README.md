# cassandra-stress

[cassandra-stress](https://cassandra.apache.org/doc/latest/cassandra/tools/cassandra_stress.html)
is Apache Cassandra's built-in benchmark CLI, shipped alongside the
server in the `cassandra-tools` Debian package. It drives synthetic
write / read / mixed workloads against a running Cassandra cluster and
emits text output with per-operation-type throughput and latency
percentiles.

## Links

- **Sample benchmark** — orchestrated by [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/cassandra-stress.yml`](../../../.github/workflows/cassandra-stress.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/cassandra-stress.yml>
- **Parser** — [`src/benchzoo/parsers/cassandra_stress.py`](../../../src/benchzoo/parsers/cassandra_stress.py) *(not yet written — pending a real captured fixture)*
- **Parser tests** — [`tests/parsers/test_cassandra_stress.py`](../../../tests/parsers/test_cassandra_stress.py) *(not yet written)*

## Heavy-deviation notice

Like ClickBench, **cassandra-stress under benchzoo does not run the
canonical [sample benchmark](../../../docs/sample-benchmark.md)**
(sleep 2.15 s / tight CPU loop / 1.4 MB write / monthly change point).
cassandra-stress is a fixed-workload driver whose identity is its
built-in write / read / mixed operation set — there is no knob for
"sleep for 2.15 s then exit," and any adaptation along those lines
would produce output that no real cassandra-stress user would
recognise.

We therefore deviate on the workload axis: the three test runs are
the tool's own canonical shapes, each limited to 10,000 operations
to keep CI time bounded:

- **`write`** — `cassandra-stress write n=10000 -rate threads=4`.
  Standard write workload against cassandra-stress's default
  `standard1` table / schema.
- **`read`** — `cassandra-stress read n=10000 -rate threads=4`.
  Reads back keys the preceding `write` run inserted.
- **`mixed`** — `cassandra-stress mixed ratio(write=1,read=1) n=10000 -rate threads=4`.
  50/50 write/read mix. cassandra-stress reports per-operation-type
  latency stats in this mode (a `WRITE` block and a `READ` block in
  addition to the `Total` block).

The consequence for ground-truth tests: there is no "test 1 ≈ 2.15 s"
assertion here. Parser tests should instead assert the *structure* of
the parsed output (three result dicts with the right `test_name`
values, the expected metrics present on each, reasonable ranges for
throughput and latency given 10k ops at 4 threads on a single-node
container) against captured fixtures.

Three files are captured — `output-write.txt`, `output-read.txt`,
`output-mixed.txt` — so the parser can segment by filename and emit
three Nyrkiö JSON results with
`attributes["test_name"] ∈ {"write", "read", "mixed"}`. The mixed run
additionally carries `WRITE` and `READ` sub-blocks that the parser
may expose as `extra_info` or as additional metrics — see
*Parser notes* below.

## Running locally

```bash
act push -W .github/workflows/cassandra-stress.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/cassandra-stress-output/`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

The workflow declares a `cassandra:5` service container. **Cassandra
is slow to start** — typically 30–60 seconds on a warm image, longer
on a cold pull — so the service's healthcheck is given a long
`start-period` and `run.sh` additionally spins on
`cqlsh localhost -e "SELECT now() FROM system.local"` with a 60 s
deadline before invoking the first stress command. If the CQL wait
loop times out under `act`, the cause is almost always that the
Cassandra JVM is still warming up; re-run with the service
container already pulled, or extend the deadline.

Alternatively, with a local Cassandra instance reachable on
`localhost:9042`, `./run.sh` can be invoked directly.

## Parser notes

cassandra-stress emits a plain-text report per invocation. Three
files are produced — one per workload — and the parser consumes
each independently, emitting one Nyrkiö JSON result per file.

### Output format

A single cassandra-stress run's output has three sections, in order:

1. **Header** — reports the settings the run will use, one
   `key: value` line per option. Includes `threads`, `partition
   spec`, `batchtype`, `rate`, the keyspace / schema, etc. These are
   run parameters, not measurements.
2. **Intermediate progress lines** — one per periodic sampling
   interval while the run is in progress. Columns include the
   current op rate, partition rate, row rate, latency mean / median
   / 95 / 99 / 99.9 / max, total partitions so far, total errors,
   and elapsed time. These are progress dumps, not the final
   numbers.
3. **`Results:` block** — the final summary the parser consumes.
   After the literal `Results:` line come one `key : value` pair
   per line:

   - `Op rate` — unit `op/s`, direction `higher_is_better`.
   - `Partition rate` — unit `pk/s`, direction `higher_is_better`.
   - `Row rate` — unit `row/s`, direction `higher_is_better`.
   - `Latency mean` — unit `ms`, direction `lower_is_better`.
   - `Latency median` — unit `ms`, direction `lower_is_better`.
   - `Latency 95th percentile` — unit `ms`, direction `lower_is_better`.
   - `Latency 99th percentile` — unit `ms`, direction `lower_is_better`.
   - `Latency 99.9th percentile` — unit `ms`, direction `lower_is_better`.
   - `Latency max` — unit `ms`, direction `lower_is_better`.
   - `Total partitions` — integer count.
   - `Total errors` — integer count.
   - `Total GC count` — integer count.
   - `Total GC time` — unit `s` (cassandra-stress prints GC time in
     seconds). Direction `lower_is_better`.
   - `Avg GC time` — unit `ms`, direction `lower_is_better`.
   - `StdDev GC time` — unit `ms`, direction `lower_is_better`.
   - `Total operation time` — unit `s` (wall clock of the run).

   The exact line labels are not fully stable across cassandra-stress
   versions — older 3.x / 4.x builds spelled some of them slightly
   differently (`Op rate` vs. `op rate`, `Latency mean` vs.
   `latency mean`). The parser should match case-insensitively and
   strip surrounding whitespace before splitting on `:`.

### Mixed-workload sub-blocks

The `mixed` run emits *three* `Results:` blocks rather than one —
one labelled `WRITE`, one `READ`, and one `Total`. The parser should
emit a single Nyrkiö JSON result for the `mixed` test (`test_name =
"mixed"`) populated from the `Total` block, and stash the per-type
numbers under `extra_info["write"]` and `extra_info["read"]` so
downstream consumers can drill down without the parser's output
shape diverging between `write` / `read` (one block each) and
`mixed` (three blocks).

### Header metadata → `extra_info`

The per-run settings in the header (`threads`, `partition spec`,
`batchtype`, `rate`, keyspace / table name, consistency level,
compression, operation counts) are run parameters, not
measurements, and go into `extra_info` rather than `metrics` —
matching the pgbench and ClickBench conventions.

### Failure handling

cassandra-stress exits non-zero on connection failure, schema
error, or a sustained error rate above its internal threshold, and
in those cases the `Results:` block may be absent or partially
populated. If the parser finds a file that lacks the `Results:`
header, or whose Results block is missing both `Op rate` and
`Latency mean`, it should still emit a result dict with the right
`test_name` and `passed: false`, matching the "record but do not
filter" rule in
[`docs/design.md`](../../../docs/design.md#library-boundaries).

A non-zero `Total errors` on an otherwise-successful run is **not**
a parser-level failure — record the count in metrics and leave
`passed: true`. Downstream consumers decide whether an error rate
is regression-worthy.

### Relationship to the fork

cassandra-stress is not tagged `[fork]` in
[`parser-targets.md`](../../../docs/parser-targets.md) section 3 —
the predecessor TypeScript project did not ship a cassandra-stress
parser. This is a clean-slate parser with no prior fixtures to
preserve.
