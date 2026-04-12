# junit-vanilla

Raw [JUnit 5](https://junit.org/junit5/) unit tests run via
[Maven Surefire](https://maven.apache.org/surefire/maven-surefire-plugin/),
producing standard junit XML. This is the **fallback** producer for
benchzoo's junit surface: when we have junit XML and no
producer-specific parser (`junit_pytest`, `junit_jest`, `junit_dotnet`,
`junit_go`, `junit_catch2`, `junit_playwright`, …) applies, the
`junit_vanilla` parser handles it.

## Links

- **Sample benchmark** —
  [`src/test/java/io/nyrkio/benchzoo/junit/SampleTest.java`](src/test/java/io/nyrkio/benchzoo/junit/SampleTest.java),
  built via [`pom.xml`](pom.xml), run via [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/junit-vanilla.yml`](../../../.github/workflows/junit-vanilla.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/junit-vanilla.yml>
- **Parser** — [`src/benchzoo/parsers/junit_vanilla.py`](../../../src/benchzoo/parsers/junit_vanilla.py) *(not yet written — pending a real captured fixture)*
- **Parser tests** — [`tests/parsers/test_junit_vanilla.py`](../../../tests/parsers/test_junit_vanilla.py) *(not yet written)*

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) as four
plain `@Test` methods on a single `SampleTest` class:

- **Test 1** (sleep 2.15 s) — `benchmark1()` calls `Thread.sleep(2150)`
  and declares `throws InterruptedException`.
- **Test 2** (tight CPU loop) — `benchmark2()` runs a
  `for (int i = 0; i < 1000; i++)` loop accumulating into a local
  `sink` that is then consulted via an always-false `if` so the
  compiler cannot trivially delete the loop. Unlike JMH's
  `Blackhole.consume`, this is a best-effort anti-DCE guard, not a
  harness-grade one: JUnit runs under the ordinary HotSpot JIT with no
  benchmark infrastructure, so test 2's role here is purely to exercise
  sub-millisecond parser handling, not to produce a physically
  meaningful loop time.
- **Test 3** (write 1.4 MB to /dev/null) — `benchmark3()` fills a
  `byte[1_400_000]` buffer via `java.util.Random.nextBytes(buf)`
  (seeded with 42 for deterministic payloads) and writes it through a
  `FileOutputStream("/dev/null")` opened in a try-with-resources.
- **Test 4** (monthly change point) — `benchmark4()` reads the current
  UTC month via `ZonedDateTime.now(ZoneOffset.UTC).getMonthValue()`,
  computes `2.15 + ((month mod 3) - 1)` and sleeps for that many
  seconds (converted to milliseconds for `Thread.sleep`).

### Build & run

`run.sh` invokes `mvn -q test`, which runs the
`maven-surefire-plugin` (pinned to 3.5.2) against `SampleTest`.
Surefire writes one junit XML file per test class to
`target/surefire-reports/TEST-<class>.xml` by default; since we have
exactly one test class, `run.sh` copies the single matching file to
`./output.xml` for artifact upload. Total suite wall time is dominated
by the two multi-second sleeps (tests 1 and 4) — roughly
`2.15 + ~0 + ~0 + {1.15, 2.15, 3.15}` seconds plus JVM startup, so on
the order of 5–10 seconds on a GitHub-hosted runner.

## Running locally

```bash
act push -W .github/workflows/junit-vanilla.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/junit-vanilla-output/output.xml`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with Java 17 and Maven installed locally, you can bypass
`act` entirely and run `bash run.sh` from this directory.

## Parser notes

`junit_vanilla` consumes raw Surefire junit XML — the usual
`<testsuite>/<testcase>` shape, where each `<testcase>` carries a
`name` attribute (the JUnit test method name), a `classname` attribute
(the fully-qualified class), and — crucially — a `time` attribute
giving wall-clock duration in seconds. That `time` attribute is the
only metric this parser emits: a single `duration` measurement per
testcase, unit `s`, `lower_is_better`.

Test names map directly: Surefire writes `name="benchmark1"` (no
`test_` prefix, no `[parameters]` suffix), so the parser uses the
`name` attribute verbatim as `attributes["test_name"]`. This is
different from [`junit_pytest`](../../../src/benchzoo/parsers/junit_pytest.py),
which strips the pytest-conventional `test_` prefix — vanilla JUnit has
no such convention, and the canonical sample benchmark uses the
`benchmarkN` names directly.

`<failure>` or `<error>` children on a testcase set `passed: false`
(same convention as `junit_pytest`). The classname goes into
`extra_info["classname"]` so downstream consumers can still disambiguate
same-named methods across test classes if they need to.

### Fallback status

This parser is the fallback for **any** producer-agnostic junit XML —
plain Java JUnit, Maven Surefire, Gradle's junit XML output, Ant's
`junitreport`, and any other tool emitting the baseline
`<testsuite>/<testcase>` shape with only the `time` attribute as
timing data. Producer-specific parsers
(`junit_pytest` for pytest-benchmark `<properties>`, `junit_jest` for
jest-junit's extensions, etc.) should always be preferred when they
apply, because they extract richer metrics that `junit_vanilla` cannot
see. Cross-reference
[`junit_pytest`](../../../src/benchzoo/parsers/junit_pytest.py) for the
producer-specific contrast.

### Reference fork

The predecessor TypeScript project at
[`nyrkio/change-detection`](https://github.com/nyrkio/change-detection)
shipped a junit XML parser. It is **reference-only** for benchzoo (see
[`docs/design.md`](../../../docs/design.md)): crib ideas and field
mappings if useful, but do not port the code. The Python parser is
written against a real captured fixture, not against the TypeScript.
