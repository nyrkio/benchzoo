# pgbench

[pgbench](https://www.postgresql.org/docs/current/pgbench.html) is
PostgreSQL's built-in benchmarking tool. By default it runs a TPC-B-like
workload against a schema it creates itself; with the `-f` flag it
executes arbitrary user-supplied SQL as a custom transaction and reports
latency and TPS. benchzoo uses the custom-script mode.

## Links

- **Sample benchmark** — [`benchmark1.sql`](benchmark1.sql),
  [`benchmark2.sql`](benchmark2.sql), [`benchmark3.sql`](benchmark3.sql),
  [`benchmark4.sql`](benchmark4.sql), orchestrated by [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/pgbench.yml`](../../../.github/workflows/pgbench.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/pgbench.yml>
- **Parser** — [`src/benchzoo/parsers/pgbench.py`](../../../src/benchzoo/parsers/pgbench.py) *(not yet written — pending a real captured fixture)*
- **Parser tests** — [`tests/parsers/test_pgbench.py`](../../../tests/parsers/test_pgbench.py) *(not yet written)*

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) in
pgbench idiom. pgbench was designed for SQL workloads, not arbitrary
sleeps, CPU loops, and file I/O, so each of the four tests is adapted
to a SQL-shaped equivalent. The adaptations are spelled out here so
the ground-truth assertions (test 1 latency ≈ 2150 ms, etc.) remain
meaningful even though the underlying operation is not a literal
match to the reference bash implementation.

- **Test 1** (sleep 2.15 s) — [`benchmark1.sql`](benchmark1.sql) runs
  `SELECT pg_sleep(2.15);`. `pg_sleep` accepts float seconds, so the
  non-round 2.15 goes through verbatim, and the server-side wall time
  is what pgbench reports as transaction latency.
- **Test 2** (tight CPU loop) — [`benchmark2.sql`](benchmark2.sql) runs
  a PL/pgSQL anonymous `DO $$ ... $$;` block containing an empty
  `FOR i IN 0..999 LOOP NULL; END LOOP;`. pgbench's `\`-prefixed
  client-side directives (`\set`, `\if`) do not include a loop
  construct, and pgbench scripts are not themselves PL/pgSQL — the
  `DO` block is the idiomatic way to get a server-side empty loop
  executed as a single SQL statement.
- **Test 3** (write 1.4 MB to /dev/null) — [`benchmark3.sql`](benchmark3.sql)
  runs `SELECT octet_length(repeat('x', 1400000));`, which builds a
  1,400,000-byte string on the server and returns it to pgbench. The
  byte count matches the spec; the payload crosses the client/server
  connection boundary, which for a network-shaped tool like pgbench
  is arguably a more honest "small I/O" than writing to /dev/null
  would be. The spec's "pseudo-random" is approximated with a
  constant byte because the purpose of test 3 is timing a small
  fixed-size write, not a randomness test.
- **Test 4** (monthly change point) — [`benchmark4.sql`](benchmark4.sql)
  runs a single `SELECT pg_sleep(2.15 + (EXTRACT(MONTH FROM NOW() AT TIME ZONE 'UTC')::int % 3 - 1));`.
  The UTC month is computed server-side so the value is consistent
  regardless of where the runner is physically located, matching the
  bash reference implementation's use of `date -u`.

The orchestration lives in [`run.sh`](run.sh), which invokes pgbench
four separate times (once per `benchmarkN.sql` file, each with
`-t 1 -c 1 -j 1 -n`) and concatenates the outputs into a single
`output.txt` with `=== benchmarkN ===` separator lines between
blocks. Unlike hyperfine, pgbench has no single-invocation "run all of
these" mode, so the four runs are stitched together by the script
instead of by the tool.

## Running locally

```bash
act push -W .github/workflows/pgbench.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/pgbench-output/output.txt`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

The workflow declares a `postgres:16` service container, which `act`
supports via Docker's own networking — no extra flags are usually
needed beyond what the hyperfine example uses. If the runner container
cannot reach the service container by the `localhost` hostname under
`act` (this sometimes happens when `act` wires services onto a bridge
network that the job container isn't attached to), rerun with
`--bind` or set `PGHOST` to the service's container name / bridge IP
as an override — the workflow reads `PGHOST` from the environment, so
a local override is a one-variable change.

Alternatively, with a local PostgreSQL instance available and the
`PG*` environment variables exported, you can bypass `act` entirely
and just run `./run.sh` from this directory.

## Parser notes

pgbench adapts the canonical sample benchmark to SQL-shaped workloads
(`pg_sleep` for sleeps, `repeat()` for the 1.4 MB payload, a PL/pgSQL
`DO` block for the empty loop). The adaptations are opinionated —
spelled out in the *Sample benchmark* section above — and the parser
needs to be aware of them so the ground-truth assertions stay
meaningful: test 1's reported latency should still land in the
2.0–2.3 s band, test 4's still in `{1.15, 2.15, 3.15}`, and so on.

### Output format

pgbench's text output for a single run looks like:

```
transaction type: benchmark1.sql
scaling factor: 1
query mode: simple
number of clients: 1
number of threads: 1
number of transactions per client: 1
number of transactions actually processed: 1/1
latency average = 2150.342 ms
tps = 0.465 (including connections establishing)
tps = 0.468 (excluding connections establishing)
```

Because we run pgbench four separate times (one invocation per
`benchmarkN.sql`), `output.txt` contains four of these blocks
concatenated together, each preceded by a `=== benchmarkN ===` marker
line written by `run.sh`. The parser splits on that marker to
segment the file; within each block, the `transaction type:` line
carries the script filename (e.g. `benchmark1.sql`), and stripping
the `.sql` suffix gives the `attributes["test_name"]`. The parser
should prefer the `transaction type:` line over the `===` marker
as the source of truth for `test_name` — the marker exists as a
splitter, not as the identifier.

### Metrics

Each block maps to one Nyrkiö JSON test result. The parser should emit:

- `latency_average` — unit `"ms"`, direction `"lower_is_better"`. Parsed
  from the `latency average = <float> ms` line. Test 1's value should
  land near 2150 ms, which is the first place to grep when
  reverse-engineering the format against a real capture.
- `tps_including_connections` — unit `"ops/s"`, direction
  `"higher_is_better"`. Parsed from the
  `tps = <float> (including connections establishing)` line.
- `tps_excluding_connections` — unit `"ops/s"`, direction
  `"higher_is_better"`. Parsed from the
  `tps = <float> (excluding connections establishing)` line.

With `-t 1` the two TPS numbers are nearly meaningless (one transaction
over ~2.15 s is ~0.46 TPS) but they are still the fields pgbench emits
and downstream consumers are used to seeing. Emitting them keeps the
pgbench parser output shape consistent with what people expect from the
tool, and it gives parser tests something to assert against even for
the non-latency-dominated tests.

### Header metadata → `extra_info`

The header lines above `latency average` (`scaling factor`,
`query mode`, `number of clients`, `number of threads`,
`number of transactions per client`,
`number of transactions actually processed`) are per-run parameters,
not measurements. They belong in `extra_info`, not in `metrics`. The
parser should stash them there (numeric where natural, string
otherwise) so downstream consumers can see what configuration produced
the numbers without having to re-derive it from the source.

### Failure handling

pgbench exits non-zero on connection failure or SQL error and prints
the error to stderr ahead of its usual summary, which may then be
missing or truncated. If the parser finds a block that lacks either
the `latency average` line or both `tps` lines, it should emit the
test result with whatever metrics it did find and set `passed: false`,
matching the "record but do not filter" rule in
[`docs/design.md`](../../../docs/design.md#library-boundaries). A
completely empty block (pgbench crashed before producing any output
for this test) should still produce a result dict with the correct
`test_name` and `passed: false`, just with an empty `metrics` list.

### Relationship to the fork

The predecessor TypeScript project at `nyrkio/change-detection` did
not ship a pgbench parser (pgbench is not tagged `[fork]` in
[`parser-targets.md`](../../../docs/parser-targets.md) section 3).
This is a clean-slate parser with no prior fixtures or design
decisions to preserve.
