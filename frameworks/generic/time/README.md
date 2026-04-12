# time (Unix `time` — bash builtin and GNU `/usr/bin/time -v`)

Unix `time` is the lowest-common-denominator CLI timing tool: it runs a
command, measures wall / user / system CPU time, and prints a summary.
There are two separate implementations in common use, with *different
output formats*, and benchzoo captures and parses both:

1. **bash's builtin `time` keyword** — always available wherever bash is.
   Emits the classic three-line `real`/`user`/`sys` summary to stderr.
2. **GNU `/usr/bin/time -v`** — a separate binary (Debian/Ubuntu package
   `time`). The `-v` flag selects the verbose multi-line format with
   max resident set size, page faults, CPU percent, context switches,
   etc.

The two formats are different enough that they warrant **separate
parser modules**, not a shared one with format auto-detection. See
*Parser notes* below.

## Links

- **Sample benchmark** — [`benchmark1.sh`](benchmark1.sh),
  [`benchmark2.sh`](benchmark2.sh), [`benchmark3.sh`](benchmark3.sh),
  [`benchmark4.sh`](benchmark4.sh), orchestrated by [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/time.yml`](../../../.github/workflows/time.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/time.yml>
- **Parsers** —
  [`src/benchzoo/parsers/time_builtin.py`](../../../src/benchzoo/parsers/time_builtin.py)
  *(not yet written — pending a real captured fixture)* and
  [`src/benchzoo/parsers/time_gnu.py`](../../../src/benchzoo/parsers/time_gnu.py)
  *(not yet written)*
- **Parser tests** —
  [`tests/parsers/test_time_builtin.py`](../../../tests/parsers/test_time_builtin.py)
  and
  [`tests/parsers/test_time_gnu.py`](../../../tests/parsers/test_time_gnu.py)
  *(not yet written)*

The predecessor TypeScript project at
[`nyrkio/change-detection`](https://github.com/nyrkio/change-detection)
had a `time` parser (contributed by the user). It's **reference-only**
for benchzoo — we don't import from it, and the Python parsers will be
written from scratch against the captured fixtures this workflow
produces.

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) in
Unix `time` idiom:

- **Test 1** (sleep 2.15 s) — [`benchmark1.sh`](benchmark1.sh) runs
  `sleep 2.15`. Both `time` implementations should report a `real`
  wall time of ~2.15 s.
- **Test 2** (tight CPU loop) — [`benchmark2.sh`](benchmark2.sh) runs
  `for ((i=0; i<1000; i++)); do :; done` in bash. Bash is interpreted,
  so the loop is not optimized away and no `black_box` equivalent is
  needed. The measured `real` time is dominated by bash process startup
  (a few ms), not the loop itself — that's fine; the point of test 2
  is to exercise the parser on small durations.
- **Test 3** (write 1.4 MB to /dev/null) — [`benchmark3.sh`](benchmark3.sh)
  runs `head -c 1400000 /dev/urandom > /dev/null`.
- **Test 4** (monthly change point) — [`benchmark4.sh`](benchmark4.sh)
  computes `2.15 + ((month mod 3) - 1)` in UTC and sleeps for that
  many seconds, producing the deterministic `{1.15, 2.15, 3.15}`
  cycle used for the change-detection showcase.

The orchestration lives in [`run.sh`](run.sh), which runs each of the
four benchmarks **twice** — once under the bash builtin and once under
`/usr/bin/time -v` — and concatenates the outputs to two separate
files, `output-builtin.txt` and `output-gnu.txt`, with plain-text
separators between each per-test block so a parser can key each block
to a `test_name`.

Keeping the invocation in a shell script (rather than inline in the
workflow YAML) makes it easy to iterate locally.

## Running locally

```bash
act push -W .github/workflows/time.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured outputs land at
`/tmp/benchzoo-artifacts/<run-id>/time-output/output-builtin.txt`
and `/tmp/benchzoo-artifacts/<run-id>/time-output/output-gnu.txt`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with `/usr/bin/time` installed locally (`sudo apt-get
install -y time` on Debian/Ubuntu), run `./run.sh` from this directory
directly. That produces the same two output files without the GitHub
Actions artifact plumbing.

## Parser notes

Two separate parser modules, one per output format. Both are split on
purpose: the formats don't share field sets, units, or layout, so a
single parser would need format auto-detection and two disjoint code
paths — cleaner to ship them as two files.

### `time_builtin` — bash's builtin `time`

The bash builtin keyword (not a command — it can't be stored in a
variable, aliased, or called via `$(which time)`; it must appear inline
in a pipeline) prints to stderr exactly three lines after the timed
command finishes:

```
real    0m2.155s
user    0m0.001s
sys     0m0.001s
```

- **Format:** `<label>\t<Xm>Y.ZZZs`, where `X` is minutes and `Y.ZZZ`
  is seconds (milliseconds precision on Linux). On long runs, minutes
  may be non-zero (e.g. `1m3.400s`); the parser must convert
  `X*60 + Y.ZZZ` to total seconds.
- **Fields mapped to Nyrkiö metrics:**
  - `real` → metric `name="real"`, `unit="s"`, `direction="lower_is_better"`
  - `user` → metric `name="user"`, `unit="s"`, `direction="lower_is_better"`
  - `sys`  → metric `name="sys"`,  `unit="s"`, `direction="lower_is_better"`
- **Direction:** `lower_is_better` for all three — every value is a
  duration.
- **Test identity:** `run.sh` writes a plain-text separator
  `=== benchmark1 (bash builtin time) ===` before each block and
  `=== end benchmark1 ===` after, so the parser splits on those
  markers and uses the captured name as `attributes["test_name"]`.
- **No stats:** the builtin reports a single measurement per run, no
  mean/stddev. If statistics are wanted, run multiple times and
  aggregate in a higher layer — or use hyperfine, which is purpose-built
  for that.
- **Failure handling:** if the timed command exits non-zero, bash still
  prints the three `time` lines. The parser should set `passed: false`
  when it can detect failure (e.g. from a non-zero exit recorded
  alongside the block), but at the moment the output format itself
  does not carry an exit code — the parser will treat every block as
  `passed: true` unless/until the fixture layout is extended to carry
  exit status.

### `time_gnu` — GNU `/usr/bin/time -v`

The `-v` ("verbose") format is a fixed multi-line block of ~23
`Label: value` pairs, one per line, produced by `/usr/bin/time` from
the GNU `time` project. Example of one block:

```
	Command being timed: "./benchmark1.sh"
	User time (seconds): 0.00
	System time (seconds): 0.00
	Percent of CPU this job got: 0%
	Elapsed (wall clock) time (h:mm:ss or m:ss): 0:02.15
	Average shared text size (kbytes): 0
	Average unshared data size (kbytes): 0
	Average stack size (kbytes): 0
	Average total size (kbytes): 0
	Maximum resident set size (kbytes): 2048
	Average resident set size (kbytes): 0
	Major (requiring I/O) page faults: 0
	Minor (reclaiming a frame) page faults: 115
	Voluntary context switches: 4
	Involuntary context switches: 1
	Swaps: 0
	File system inputs: 0
	File system outputs: 0
	Socket messages sent: 0
	Socket messages received: 0
	Signals delivered: 0
	Page size (bytes): 4096
	Exit status: 0
```

- **Fields mapped to Nyrkiö metrics** (not exhaustive — parser picks
  the useful subset, all `lower_is_better` unless noted):
  - `Elapsed (wall clock) time` → metric `name="real"`, `unit="s"`.
    Format is `h:mm:ss.ff` or `m:ss.ff`; parser must convert to total
    seconds.
  - `User time (seconds)` → metric `name="user"`, `unit="s"`.
  - `System time (seconds)` → metric `name="sys"`, `unit="s"`.
  - `Percent of CPU this job got` → metric `name="cpu_percent"`,
    `unit="%"`. Strip the trailing `%`.
  - `Maximum resident set size (kbytes)` → metric `name="max_rss"`,
    `unit="kB"` (decimal kilobytes — see note below).
  - `Major (requiring I/O) page faults` → metric `name="page_faults_major"`,
    `unit="count"`.
  - `Minor (reclaiming a frame) page faults` → metric
    `name="page_faults_minor"`, `unit="count"`.
  - `Voluntary context switches` → metric `name="ctx_switches_voluntary"`,
    `unit="count"`.
  - `Involuntary context switches` → metric
    `name="ctx_switches_involuntary"`, `unit="count"`.
  - `File system inputs`, `File system outputs` → metrics `fs_inputs`,
    `fs_outputs`, `unit="count"`.
- **Units gotcha:** GNU time documents its memory figures in
  "kbytes", but historically on Linux the value is reported in
  **kibibytes** (1024 bytes). We follow the source and label the unit
  `"kB"`; any downstream consumer that cares about the distinction can
  consult this note. Don't try to convert.
- **Direction:** `lower_is_better` for durations, memory, page faults,
  context switches, fs IO. `cpu_percent` has no universally-agreed
  direction (higher means more work packed into wall time, but also
  means less I/O wait) — the parser should omit `direction` for
  `cpu_percent`.
- **Test identity:** same separator convention as the builtin path —
  `run.sh` writes `=== benchmark1 (/usr/bin/time -v) ===` before each
  block and `=== end benchmark1 ===` after.
- **Failure handling:** GNU time records `Exit status: N` as the last
  line of the verbose block. The parser should read that and set
  `passed: false` when `N != 0`. It still emits metrics for failed
  runs (per the "record, don't filter" rule in
  [`docs/design.md`](../../../docs/design.md)).
- **Availability:** `/usr/bin/time` is **not** installed by default on
  `ubuntu-latest`. The workflow `apt-get install -y time`s it
  explicitly. Locally, install it the same way.
