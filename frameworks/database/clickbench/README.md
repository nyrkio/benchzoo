# clickbench

[ClickBench](https://github.com/ClickHouse/ClickBench) is an analytical
(OLAP) database benchmark maintained by ClickHouse Inc. The canonical
form runs 43 fixed queries against a 70 GB `hits` dataset across dozens
of database engines and publishes a JSON result per (system, dataset,
hardware) combination. benchzoo captures the **JSON result format** so
the parser has a real fixture to consume — we do not attempt to
reproduce ClickBench's numbers or dataset.

## Links

- **Sample benchmark** — [`schema.sql`](schema.sql),
  [`queries.sql`](queries.sql), loaded by [`load.sh`](load.sh),
  orchestrated by [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/clickbench.yml`](../../../.github/workflows/clickbench.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/clickbench.yml>
- **Parser** — [`src/benchzoo/parsers/clickbench.py`](../../../src/benchzoo/parsers/clickbench.py) *(not yet written — pending a real captured fixture)*
- **Parser tests** — [`tests/parsers/test_clickbench.py`](../../../tests/parsers/test_clickbench.py) *(not yet written)*

## Heavy-deviation notice

Unlike the other framework directories, **ClickBench under benchzoo
does not run the canonical [sample benchmark](../../../docs/sample-benchmark.md)**
(sleep 2.15 s / tight CPU loop / 1.4 MB write / monthly change point).
ClickBench is a full-dataset SQL benchmark whose identity is its
query set and data shape — swapping in `pg_sleep`-style adaptations
(the pgbench approach) would produce a file in ClickBench's JSON
shape that doesn't actually exercise anything ClickBench users would
recognise, and would not help the parser because ClickBench's result
format is indexed by query position, not by test name.

We therefore deviate on two axes:

- **Dataset.** Upstream uses a 70 GB `hits.tsv` dump of real traffic.
  We generate **10,000 rows (~500 KB) of synthetic TSV** in
  [`load.sh`](load.sh) with seeded `random` so the load is deterministic
  and finishes in a second or two. The schema in [`schema.sql`](schema.sql)
  is a trimmed 10-column subset of the canonical `hits` table; column
  names match upstream so the query bodies are directly comparable.
- **Query set.** Upstream runs 43 queries. We run **5** representative
  shapes from [`queries.sql`](queries.sql):
  1. `SELECT count(*) FROM hits` — the canonical Q0.
  2. Filtered count on `IsMobile` — canonical Q1 shape.
  3. `count(DISTINCT UserID)` — canonical Q5 shape.
  4. Top-10 `RegionID` by frequency — canonical Q7 shape.
  5. `AVG(ResolutionWidth)` grouped by `Title` with a URL-prefix
     `WHERE` — canonical Q20 shape.

The consequence for ground-truth tests: there is no "test 1 ≈ 2.15 s"
assertion here. Parser tests should instead assert the *structure* of
the parsed output (5 query results, 3 runs each, all non-negative
floats, expected metadata fields present) against a captured fixture.

## Running locally

```bash
act push -W .github/workflows/clickbench.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/clickbench-output/output.json`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

The workflow declares a `clickhouse/clickhouse-server:24.12-alpine`
service container. Locally, with a ClickHouse server available and
`CLICKHOUSE_HOST` exported, `./run.sh` can also be invoked directly.

## Parser notes

The upstream result format (see
<https://github.com/ClickHouse/ClickBench/tree/main/clickhouse>) is a
single JSON document per run with the following top-level keys:

| Key            | Type           | Meaning                                                         |
| -------------- | -------------- | --------------------------------------------------------------- |
| `system`       | string         | Database engine name (e.g. `"ClickHouse"`, `"DuckDB"`).         |
| `date`         | `YYYY-MM-DD`   | Calendar date of the run. **Not the git commit timestamp.**    |
| `machine`      | string         | Free-form hardware tag (upstream uses `"c6a.4xlarge"` etc.).   |
| `cluster_size` | int            | Number of nodes. `1` for single-node.                           |
| `comment`      | string         | Free-form.                                                      |
| `tags`         | list[string]   | e.g. `["column-oriented", "OLAP"]`.                             |
| `load_time`    | float seconds  | Wall time of the initial data load.                             |
| `data_size`    | int bytes      | On-disk size after load.                                        |
| `result`       | list[list[float]] | **The measurements.** One inner list per query, in the order of the canonical query set. Each inner list holds the wall times in seconds for three repeated runs of that query. |

### Mapping to Nyrkiö JSON

- **One result dict per query.** A ClickBench run with 43 queries
  produces 43 entries in `parse()`'s output list; our trimmed fixture
  produces 5.
- **`attributes["test_name"]`** is the query index, not the SQL text.
  Upstream identifies queries by position (0-based in the JSON, 1-based
  in the markdown reports). Use **`"q1"`, `"q2"`, ... `"q43"`** as the
  test name — stable across runs and matches how ClickBench's own
  result tables are labelled.
- **Metrics per query.** Each query contributes at least three runs.
  The parser should emit per-run metrics plus a derived aggregate:
  - `run_1`, `run_2`, `run_3` — unit `"s"`, direction
    `"lower_is_better"`. The raw values from the inner array.
  - `min` — unit `"s"`, direction `"lower_is_better"`. Minimum of the
    three runs; upstream's reports use the minimum as the headline
    number because cold-cache effects push `run_1` higher than the
    warm-cache `run_2`/`run_3`.
- **`extra_info`** gets the top-level document metadata that is common
  to every query in the run: `system`, `date`, `machine`,
  `cluster_size`, `comment`, `tags`, `load_time`, `data_size`. The same
  values are copied onto every result dict so downstream consumers can
  filter/group without needing the enclosing wrapper.
- **`timestamp`** is always `0` per the parser contract in
  [`docs/design.md`](../../../docs/design.md). The `date` field above
  is wall-clock of the run, not commit time, and goes into
  `extra_info["date"]` — do not use it for `timestamp`.

### Failure handling

ClickBench's JSON uses the string `"nan"` (or sometimes the JSON
literal `null`) inside the `result` arrays for queries that failed or
were skipped on a given system. The parser should:

- Treat `"nan"` / `null` / missing run values as a failed run.
- Still emit a result dict for that query with `passed: false`.
- Record whatever numeric runs succeeded; emit no metric for the ones
  that didn't, rather than pushing a sentinel value.

### Relationship to the fork

ClickBench is not tagged `[fork]` in
[`parser-targets.md`](../../../docs/parser-targets.md) section 3 —
the predecessor TypeScript project did not ship a ClickBench parser.
This is a clean-slate parser with no prior fixtures to preserve.
