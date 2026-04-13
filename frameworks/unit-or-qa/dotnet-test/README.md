# dotnet-test (TRX)

`dotnet test` is the .NET SDK's built-in test runner; it drives any
test framework that ships a Visual Studio test adapter (xUnit, NUnit,
MSTest). Running with `--logger trx` emits a TRX (Visual Studio Test
Results) XML file containing per-test outcome and wall-clock duration —
Microsoft's native test-report format, distinct from JUnit XML.

This directory exercises `dotnet test` against an xUnit test project
and captures its TRX output. The `--logger junit` variant of
`dotnet test` is a separate framework directory with its own parser.

## Links

- **Sample benchmark** — [`SampleTests.cs`](SampleTests.cs),
  [`SampleTests.csproj`](SampleTests.csproj), orchestrated by
  [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/dotnet-test.yml`](../../../.github/workflows/dotnet-test.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/dotnet-test.yml>
- **Parser** — [`src/benchzoo/parsers/dotnet_test.py`](../../../src/benchzoo/parsers/dotnet_test.py) *(not yet written — pending a real captured fixture)*
- **Parser tests** — [`tests/parsers/test_dotnet_test.py`](../../../tests/parsers/test_dotnet_test.py) *(not yet written)*

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) in
xUnit-on-`dotnet test` idiom:

- **Test 1** (sleep 2.15 s) — `Benchmark1()` is a `[Fact]` that calls
  `Thread.Sleep(2150)`. `dotnet test` records the wall-clock duration
  of the method call as the TRX `duration` attribute.
- **Test 2** (tight CPU loop) — `Benchmark2()` accumulates `0..1000`
  into `sum` and feeds the result into `Assert.True(sum >= 0)`. The
  assertion keeps the JIT from eliding the loop. The *loop* itself is
  sub-microsecond, but the TRX `duration` will be dominated by xUnit's
  per-test overhead (tens of milliseconds typically). That is
  expected — unlike BenchmarkDotNet, `dotnet test` has no
  pilot/warmup/iteration loop to isolate the method body from
  test-runner overhead. The ground-truth assertion for test 2 in the
  parser tests accepts a wide range for exactly this reason.
- **Test 3** (write 1.4 MB to /dev/null) — `Benchmark3()` fills a
  `byte[1_400_000]` from a seeded `Random` and writes it to
  `File.OpenWrite("/dev/null")`. `/dev/null` is Unix-only, so this
  test would throw on Windows. The workflow pins
  `runs-on: ubuntu-latest` to match.
- **Test 4** (monthly change point) — `Benchmark4()` reads
  `DateTime.UtcNow.Month` (UTC is load-bearing — see
  [`docs/sample-benchmark.md`](../../../docs/sample-benchmark.md#formula))
  and sleeps for `2.15 + ((m % 3) - 1)` seconds.

### Why xUnit specifically

`dotnet test` itself is framework-agnostic — it drives whichever test
framework the project references via its VS test adapter. We pick
xUnit here because it is the most common choice in modern .NET
projects and the `[Fact]` attribute has the minimal ceremony needed
for four independent methods. The TRX output shape is the same
regardless of which adapter produced the results (xUnit, NUnit,
MSTest), so the parser that ingests this fixture will happily consume
TRX from any of them.

## Running locally

```bash
act push -W .github/workflows/dotnet-test.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/dotnet-test-output/output.trx`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with the .NET 8 SDK installed locally, you can bypass
`act` entirely and just run `./run.sh` from this directory. That
produces the same `output.trx` without the GitHub Actions artifact
plumbing.

## Parser notes

TRX is XML. The top-level element is `<TestRun>` (in the namespace
`http://microsoft.com/schemas/VisualStudio/TeamTest/2010` — any TRX
parser needs to handle that default namespace, typically by stripping
it or by registering a prefix). Under `<TestRun>` the two sections
relevant here are:

- **`<Results>`** — one `<UnitTestResult>` per test method, in order
  of completion. The attributes that matter:
  - `testName` — the unqualified method name, e.g. `"Benchmark1"`.
    **No type/namespace prefix** — TRX records just the short method
    name in this attribute (the full name is on the sibling
    `<TestDefinition>` entry, under `<UnitTest>` → `<TestMethod
    className="..." name="..."/>`). So the parser can read
    `testName` directly without stripping.
  - `duration` — wall-clock time in `hh:mm:ss.fffffff` format, e.g.
    `"00:00:02.1534567"`. **This is not seconds** — the parser must
    split on `:` and `.`, convert to seconds (or ns, etc.), and emit
    the result with the correct unit. A naive `float(duration)` will
    silently produce wrong values.
  - `outcome` — `"Passed"`, `"Failed"`, `"NotExecuted"`, `"Timeout"`,
    `"Aborted"`, etc. Parsers set `passed: true` for `"Passed"` and
    `passed: false` for anything else (following the "record but
    don't filter" rule in
    [`docs/design.md`](../../../docs/design.md)).
  - `startTime` / `endTime` — ISO 8601 timestamps for each test.
    **Not eligible for the Nyrkiö `timestamp` field** — parsers
    always set `timestamp: 0` and the ingest layer fills in the git
    commit timestamp later. If you want to preserve the wall-clock
    run time for reference, stash it in `extra_info` (e.g.
    `extra_info["machine_time"]`).
  - `testId`, `executionId` — GUIDs. Not interesting for the
    time-series use case; skip.

- **`<ResultSummary>`** — overall counters (total / passed / failed
  / etc.) plus a `<Output>` section that may contain captured stdout
  from failed tests. Not needed for per-test durations; skip unless
  you want failure detail.

### Mapping to Nyrkiö JSON

- `attributes["test_name"]` ← `UnitTestResult/@testName`
  (e.g. `"Benchmark1"`). **Judgment call for the user:** the C#
  convention is PascalCase, but every other framework's canonical
  sample uses lowercase `"benchmark1"` etc. The parser may choose
  to lowercase the `testName` value to keep cross-framework
  `test_name` values uniform, or preserve PascalCase and let
  downstream queries cope. Flag this decision when the parser is
  written — and, if chosen, apply the same rule in the
  BenchmarkDotNet parser so the two .NET parsers agree.
- `metrics` — one entry with `name: "duration"`, `unit: "s"` (or
  `"ns"` if you prefer to match the BenchmarkDotNet parser's internal
  unit; either is fine as long as it's consistent),
  `direction: "lower_is_better"`, and `value` computed from the
  `duration` attribute. Formula:
  `h*3600 + m*60 + int_seconds + fractional_seconds`. The seven-digit
  fractional component is 100-nanosecond "ticks" — each digit has the
  same meaning as a decimal fraction of a second, so a naive string
  split-and-float works fine. TRX carries no stddev / percentile /
  iteration breakdown — it's a single duration per test.
- `timestamp` — **always `0`.** Do not read `startTime` / `endTime`
  / `ResultSummary.StartTime` for this field.
- `passed` — `true` iff `outcome="Passed"`; `false` otherwise. Tests
  with `outcome="NotExecuted"` are still recorded (they have a
  `duration` of `"00:00:00.0000000"`) — "record but don't filter".
- `extra_info` — optional. Candidates: `outcome` (the raw string, in
  case a downstream consumer wants to distinguish `"Failed"` from
  `"Timeout"`), `machine_time` from `startTime`, computer name from
  `UnitTestResult/@computerName`.

### The `hh:mm:ss.fffffff` duration format

Worth dwelling on because it's the single load-bearing parser detail.
Example values:

- `"00:00:02.1534567"` — 2.1534567 seconds (test 1 territory)
- `"00:00:00.0123456"` — 12.3456 ms (test 2 territory, dominated by
  runner overhead)
- `"00:00:00.0004521"` — 452.1 µs (test 3 territory)

The seven fractional digits are .NET `TimeSpan.Ticks` expressed as a
decimal fraction: one tick is 100 ns, so the smallest representable
duration is 0.0000001 s = 100 ns. Durations smaller than that round
to zero in the TRX output. For the canonical sample benchmark this
only matters for test 2 (tight CPU loop), and in practice the
xUnit-per-test overhead keeps test 2's recorded duration well above
the tick floor — you'll see ~milliseconds, not zeros.

### Reference prior art

The fork at [nyrkio/change-detection][fork] did not ship a TRX parser;
this is a greenfield parser for benchzoo. The JUnit variant of
`dotnet test` (with `--logger junit`) is a separate framework
directory and parser, so TRX is the only place TRX-specific parsing
logic lives.

[fork]: https://github.com/nyrkio/change-detection
