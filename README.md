# benchzoo

Parsers that convert benchmark-framework, load-tester, and unit-test-runner
output into a uniform JSON shape, plus a self-testing corpus of the same
canonical benchmark implemented in every supported framework.

- **Design:** [`docs/design.md`](docs/design.md)
- **Parser targets:** [`docs/parser-targets.md`](docs/parser-targets.md)
- **Canonical sample benchmark:** [`docs/sample-benchmark.md`](docs/sample-benchmark.md)
- **Workflow conventions:** [`docs/workflow-conventions.md`](docs/workflow-conventions.md)
- **Current plan:** [`PLAN.md`](PLAN.md)

## Layout

```
src/benchzoo/parsers/   # Python parser modules, one per format
tests/parsers/          # pytest tests, table-driven from captured fixtures
frameworks/<category>/  # sample benchmark implementations per framework
  language/             #   dedicated benchmark libraries (criterion, JMH, ...)
  loadtest/             #   k6, JMeter, Gatling, Locust, wrk, ...
  database/             #   sysbench, pgbench, ClickBench, ...
  ml-ai/                #   MLPerf, vLLM, ...
  frontend/             #   Lighthouse, WebPageTest, sitespeed.io
  unit-or-qa/           #   junit-* per producer, go test -json, ...
  generic/               #   time, hyperfine, custom JSON/CSV escape hatches
.github/workflows/      # one <framework>.yml per framework, mirrors frameworks/
```

Each framework directory ships the canonical four-test sample benchmark
(see [`docs/sample-benchmark.md`](docs/sample-benchmark.md)) in that
framework's idiom, a workflow that runs it on push/PR and uploads the
captured native output as a GitHub Actions artifact, and a parser module
that consumes the captured output. The parsers are the library; the
frameworks/ tree is the self-testing corpus.

## Status

Pre-alpha. Planning phase is complete; implementation is underway.
See [`PLAN.md`](PLAN.md) for the current session's scope.
