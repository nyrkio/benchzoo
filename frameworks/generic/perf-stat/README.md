# perf stat (Linux `perf stat` — hardware/software counter wrapper)

`perf stat` is the counter-reading mode of Linux `perf(1)`, the kernel's
standard performance-analysis tool (part of the `linux-tools-*` Debian /
Ubuntu packages). Like Unix `time`, it wraps a subprocess and prints a
summary after the command exits — but instead of just wall / user /
system time, it reports a rich set of hardware and software event
counters: CPU cycles, retired instructions, cache references, cache
misses, branches, branch-misses, context switches, page faults, and
(on supported hardware) energy / power events.

benchzoo captures both of the formats perf natively emits:

1. **Default text format** — the human-readable block with one line per
   counter plus a `X.XX seconds time elapsed` footer.
2. **CSV format** (`-x,`) — machine-readable, one line per counter,
   columns separated by `,`.

The two are different enough that they warrant **separate parser
modules**, not a shared one with auto-detection. See *Parser notes*
below.

## Links

- **Sample benchmark** — [`benchmark1.sh`](benchmark1.sh),
  [`benchmark2.sh`](benchmark2.sh), [`benchmark3.sh`](benchmark3.sh),
  [`benchmark4.sh`](benchmark4.sh), orchestrated by [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/perf-stat.yml`](../../../.github/workflows/perf-stat.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/perf-stat.yml>
- **Parsers** —
  [`src/benchzoo/parsers/perf_stat_text.py`](../../../src/benchzoo/parsers/perf_stat_text.py)
  *(not yet written — pending a real captured fixture)* and
  [`src/benchzoo/parsers/perf_stat_csv.py`](../../../src/benchzoo/parsers/perf_stat_csv.py)
  *(not yet written)*
- **Parser tests** —
  [`tests/parsers/test_perf_stat_text.py`](../../../tests/parsers/test_perf_stat_text.py)
  and
  [`tests/parsers/test_perf_stat_csv.py`](../../../tests/parsers/test_perf_stat_csv.py)
  *(not yet written)*

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) wrapped
under `perf stat`:

- **Test 1** (sleep 2.15 s) — [`benchmark1.sh`](benchmark1.sh). perf
  should report `task-clock` of ~2150 msec and a `time elapsed`
  footer of ~2.15 seconds. Most hardware counters (cycles,
  instructions) will be near-zero since the process is sleeping, not
  computing.
- **Test 2** (tight CPU loop) — [`benchmark2.sh`](benchmark2.sh). The
  loop itself runs in microseconds; most wall time is bash startup.
  Useful as a sub-millisecond counter-values test.
- **Test 3** (write 1.4 MB to /dev/null) — [`benchmark3.sh`](benchmark3.sh).
  Most time is in `/dev/urandom` kernel work; `context-switches` and
  `page-faults` will likely be non-zero.
- **Test 4** (monthly change point) — [`benchmark4.sh`](benchmark4.sh).
  Same shape as test 1 with a month-dependent sleep; `task-clock` is
  the change-detection signal.

The orchestration lives in [`run.sh`](run.sh), which runs each of the
four benchmarks **twice** — once with the default text format and once
with `-x,` (CSV) — and concatenates the outputs into
`output-text.txt` and `output-csv.txt`, with `=== benchmarkN (...) ===`
separators between blocks so a parser can key each block to a
`test_name`.

## Running locally

```bash
act push -W .github/workflows/perf-stat.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured outputs land at
`/tmp/benchzoo-artifacts/<run-id>/perf-stat-output/output-text.txt`
and `.../output-csv.txt`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with perf installed locally (`sudo apt-get install -y
linux-tools-generic linux-tools-$(uname -r)` on Debian/Ubuntu), run
`./run.sh` from this directory directly. You may need to lower
`kernel.perf_event_paranoid` first — see *Known limitation* below.

## Known limitation: perf and GitHub Actions

**`perf stat` may not produce useful counter data on GitHub-hosted
runners.** The `kernel.perf_event_paranoid` sysctl controls what
unprivileged users can measure:

| `perf_event_paranoid` | What unprivileged users can do                      |
| --------------------: | --------------------------------------------------- |
|                   −1  | Everything, including raw tracepoints.              |
|                    0  | CPU, kernel, and user-space profiling.              |
|                    1  | Kernel + user profiling (not raw tracepoints).      |
|                    2  | User-space profiling only. **Default on many distros.** |
|                    3  | No user-space profiling either.                     |
|                    4  | Nothing — perf refuses to open any event. (Some hardened kernels.) |

GitHub-hosted `ubuntu-latest` runners have historically shipped with
`perf_event_paranoid=4`, at which point `perf stat` opens zero
counters and either exits non-zero or prints `<not supported>` for
every event. `sudo sysctl -w kernel.perf_event_paranoid=1` *may* work
— sudo is available on the runner — but is not guaranteed across
future runner image changes, and in sandboxed / Docker-in-Docker
setups (`act`) it typically fails outright.

The workflow attempts the sysctl lowering as a best-effort and then
runs `run.sh` regardless. When perf fails, `run.sh` captures the
error message inline in the output file rather than aborting, so the
artifact upload still succeeds and the fixture records *what actually
happened* on this runner. A reader inspecting the artifact will see
either real counter blocks (ideal) or error messages plus
`perf --version` (the fallback fixture).

For local development under `act`, expect to either (a) run the
container privileged, or (b) treat the GitHub-produced fixture as the
source of truth and iterate on the parser against whatever real perf
output we're able to collect from a non-sandboxed machine.

## Parser notes

Two separate parser modules, one per output format. The formats share
the *concept* of a counter block but not the layout — splitting them
keeps each parser small and avoids format auto-detection branches.

### `perf_stat_text` — default human-readable format

The default format looks roughly like this:

```
 Performance counter stats for './benchmark1.sh':

           2,150.24 msec task-clock                #    0.001 CPUs utilized
                  4      context-switches          #    1.861 /sec
                  0      cpu-migrations            #    0.000 /sec
                115      page-faults               #   53.482 /sec
        <not counted>    cycles
        <not supported>  instructions
         12,345,678      branches                  #    5.741 M/sec
             23,456      branch-misses             #    0.19% of all branches

       2.151234567 seconds time elapsed

       0.000321000 seconds user
       0.001234000 seconds sys
```

- **Per-counter line shape:** `<value>  <event-name>  # <derived-stat>`.
  The value may be a comma-formatted integer (`1,234,567,890`), a
  decimal with a unit (`2,150.24 msec`), a percentage
  (`0.19% of all branches` in the derived column — but the raw value
  on the left is never a percent), or one of the special tokens
  **`<not counted>`** (the event exists but the kernel didn't actually
  count it — often because of multiplexing) or **`<not supported>`**
  (the event isn't available on this CPU / kernel — very common under
  low `perf_event_paranoid`, and the ENTIRE output may degrade to this
  on paranoid=4). The parser must handle both tokens gracefully —
  typically by emitting the metric with `value: null` and
  `passed: false`, or by skipping it entirely (decision TBD when the
  parser is written).
- **Footer lines:** `X.XXXXXX seconds time elapsed` (wall time — this
  is the ground-truth signal for test 1, ~2.15), plus `user` and
  `sys` CPU-time lines in recent perf versions.
- **Units seen in the value column:** `msec` for `task-clock`,
  `Joules` for `power/energy-*/`, none (bare count) for everything
  else. The parser should treat `task-clock` specially — it's the
  wall-time proxy and is measured in **milliseconds** unlike every
  other time field in perf output.
- **Test identity:** `run.sh` writes `=== benchmark1 (perf stat, text) ===`
  before each block and `=== end benchmark1 ===` after.
- **Ground-truth assertion for test 1:** `task-clock` ≈ 2150 msec
  (equivalently, `time elapsed` ≈ 2.15 s). Assert
  `2000 < task_clock_msec < 2300` or `2.0 < time_elapsed_s < 2.3`.
- **Direction:** `lower_is_better` for durations, `context-switches`,
  `page-faults`, `cache-misses`, `branch-misses`. `cycles`,
  `instructions`, `branches` have no universally-correct direction
  (more isn't worse; it just means more work happened) — omit
  `direction` for those.

### `perf_stat_csv` — `-x,` format

With `-x,`, perf emits one line per counter. The column layout is:

```
<value>,<unit>,<event>,<counter_running_time_ns>,<pcnt_time_running>,<metric_value>,<metric_unit>
```

For example:

```
2150.243210,msec,task-clock:u,2150243210,100.00,0.001,CPUs utilized
4,,context-switches:u,2150243210,100.00,1.861,/sec
0,,cpu-migrations:u,2150243210,100.00,0.000,/sec
115,,page-faults:u,2150243210,100.00,53.482,/sec
<not counted>,,cycles:u,0,0.00,,
<not supported>,,instructions:u,0,0.00,,
12345678,,branches:u,2150243210,100.00,5.741,M/sec
23456,,branch-misses:u,2150243210,100.00,0.19,of all branches
```

- **Columns:**
  1. `value` — the counter. May be a decimal (for msec events), a
     bare integer, or `<not counted>` / `<not supported>`.
  2. `unit` — usually blank; populated for `task-clock` (`msec`) and
     power/energy events (`Joules`).
  3. `event` — the event name, often with a `:u` suffix indicating
     user-space-only counting (driven by `perf_event_paranoid`).
     The parser may want to strip the suffix for metric naming.
  4. `counter_running_time_ns` — how long (ns) the counter was
     actually running. With multiplexing, this is less than the total
     wall time.
  5. `pcnt_time_running` — percentage of the full run during which
     the counter was counting. `100.00` means it ran the whole time.
  6. `metric_value` — a derived metric perf computes (the
     `X.XXX /sec` or `X.XX% of all branches` seen in the text
     format). Can be blank.
  7. `metric_unit` — the unit for column 6.
- **Quoting:** most fields are unquoted integers / decimals / bare
  words. The derived-metric unit (column 7) can contain spaces
  (`of all branches`, `CPUs utilized`) — not quoted, just unescaped
  spaces. The parser must not assume the CSV is strict RFC 4180.
- **`<not counted>` / `<not supported>` rows:** same semantics as in
  the text format; columns 4–7 are typically zero or blank for these
  rows. Handle them the same way the text parser does.
- **Summary lines:** perf **does NOT emit a `time elapsed` row in
  `-x,` mode** — the wall-time signal in CSV is `task-clock` (col 1,
  unit `msec`, col 3 starts with `task-clock`). The parser uses that
  as the wall-time metric; *do not* try to recover the elapsed time
  by summing other events.
- **Test identity:** `run.sh` writes `=== benchmark1 (perf stat, csv) ===`
  before each block and `=== end benchmark1 ===` after.
- **Ground-truth assertion for test 1:** `task-clock` value ≈ 2150
  (unit column = `msec`). Assert `2000 < value_msec < 2300`.
- **Direction:** same conventions as the text parser.
- **Common events** in the default set (no `-e` flag):
  `task-clock`, `context-switches`, `cpu-migrations`, `page-faults`,
  `cycles`, `instructions`, `branches`, `branch-misses`. The exact
  list depends on the CPU / kernel; `cache-references` and
  `cache-misses` are also common.

### Failure handling

If an entire run has `<not supported>` in every value column — the
expected outcome under `perf_event_paranoid=4` — the parser should
emit a result with `passed: false` and either empty metrics or the
same metric entries with `value: null`. This is not a parse failure;
it is the environment telling us perf was blocked, and we want that
signal to surface rather than be silently swallowed. See the *Known
limitation* section above and the "record, don't filter" rule in
[`docs/design.md`](../../../docs/design.md).
