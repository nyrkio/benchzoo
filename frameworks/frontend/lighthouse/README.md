# lighthouse

[Lighthouse](https://github.com/GoogleChrome/lighthouse) is Google's
open-source web performance auditor. It loads a page in headless
Chrome and reports web-vitals metrics — Largest Contentful Paint,
First Contentful Paint, Cumulative Layout Shift, Total Blocking Time,
Speed Index, Time to Interactive, Total Byte Weight, Server Response
Time, and a composite performance score — as a structured JSON
report.

## Links

- **Sample benchmark** — a minimal static page in [`site/`](site/)
  ([`index.html`](site/index.html), [`style.css`](site/style.css)),
  served and audited by [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/lighthouse.yml`](../../../.github/workflows/lighthouse.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/lighthouse.yml>
- **Parser** — [`src/benchzoo/parsers/lighthouse.py`](../../../src/benchzoo/parsers/lighthouse.py) *(not yet written — pending a real captured fixture)*
- **Parser tests** — [`tests/parsers/test_lighthouse.py`](../../../tests/parsers/test_lighthouse.py) *(not yet written)*

## Sample benchmark

Lighthouse does not fit the
[canonical sample benchmark](../../../docs/sample-benchmark.md) cleanly.
The canonical suite was designed for frameworks that time arbitrary
code (a sleep, a CPU loop, an I/O write), and the four tests exist to
stress-test parsers across very different magnitudes. Lighthouse is a
fundamentally different kind of tool: it audits a single browser page
load and reports web-vitals metrics that are *not* under our control —
they're emergent properties of the page, the browser, and the runner
hardware. Trying to shoehorn `sleep 2.15` into LCP is nonsensical.

So the adaptation is explicit and honest: **one test run, not four.**

- **Test 1** (sleep 2.15 s) — **dropped.** Lighthouse does not measure
  arbitrary sleep; it measures web vitals of a page load. A 2.15 s
  sleep has no corresponding audit.
- **Test 2** (tight CPU loop, sub-ms) — **dropped.** Lighthouse
  timings are all in the hundreds-of-milliseconds to seconds range.
  There is no sub-ms metric to exercise.
- **Test 3** (write 1.4 MB to /dev/null) — **dropped.** Lighthouse
  does not do filesystem I/O benchmarking.
- **Test 4** (monthly change point) — **dropped.** Test 4 requires the
  parser-side timing to be under our control so we can produce a
  deterministic step function. Lighthouse timings depend on headless
  Chrome's rendering, which we can't shape into `2.15 + ((m mod 3) - 1)`
  seconds. There is therefore no `schedule:` trigger on this workflow:
  it runs on push/PR and manual dispatch only.

What the framework *does* run is a single Lighthouse audit of a
minimal static page served from `./site/`. We treat the page load as
one test with `attributes["test_name"] = "homepage"`, and emit every
headline web-vital as a separate entry in `metrics[]`.

The page itself (`site/index.html` + `site/style.css`) is deliberately
tiny — a heading, a paragraph, an inline SVG, and one external
stylesheet — so Lighthouse has real content to inspect but the audit
is fast and deterministic-ish. No external CDN references, no
third-party fonts, no analytics: everything Lighthouse sees is
committed in this directory.

The orchestration lives in [`run.sh`](run.sh), which:

1. Starts `python3 -m http.server 8080 --directory ./site` in the
   background (Lighthouse needs a real HTTP origin, not `file://`).
2. Runs `lighthouse http://localhost:8080/` with JSON output.
3. `trap`s a kill on the HTTP server so it goes away on any exit.

## Running locally

```bash
act push -W .github/workflows/lighthouse.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/lighthouse-output/output.json`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with `lighthouse` (and Chrome) installed locally, you
can bypass `act` entirely and just run `./run.sh` from this directory.
That produces the same `output.json` without the GitHub Actions
artifact plumbing.

### Note on running under `act`

Headless Chrome under Docker can be fiddly. The `--no-sandbox` flag in
`run.sh` is required — without it, Chrome refuses to start in a
container that doesn't grant `CAP_SYS_ADMIN`. If Lighthouse still
fails to launch Chrome under `act`, you may need to invoke `act` with
`--container-options "--cap-add=SYS_ADMIN"` or pick a
`catthehacker/ubuntu:full-*` image that ships Chrome pre-installed.
The `act-latest` slim image does not include Chrome. This is a
well-known rough edge, not a bug in the workflow itself — on real
GitHub `ubuntu-latest` runners Chrome is pre-installed as
`google-chrome-stable` and the workflow runs as-is.

## Parser notes

This is one of the frameworks that deviates most from the canonical
sample-benchmark shape, so parser authors need more context than
usual.

### Lighthouse JSON output format

Lighthouse's JSON report is a large, well-documented structure. The
top-level keys include:

- `requestedUrl` / `finalUrl` — the URL Lighthouse was asked to audit
  and the URL it ended up on after redirects.
- `fetchTime` — ISO 8601 wall-clock string for when the audit ran.
  **Do not use this for `timestamp`** — parsers always set
  `timestamp: 0` per the design-doc field semantics. If a parser wants
  to preserve the fetch time for reference, stash it in
  `extra_info["fetch_time"]` as a string.
- `userAgent` / `environment` — runtime info (Chrome version, host
  user agent, benchmark index).
- `runWarnings` — non-fatal warnings from the audit. Parsers may want
  to surface these in `extra_info["run_warnings"]`.
- `configSettings` — the effective Lighthouse config (throttling
  method, form factor, etc.). Useful for `extra_info`.
- `categories` — top-level category scores. For our
  `--only-categories=performance` invocation this is just
  `categories.performance.score`, a float in `[0, 1]` (or `null`).
- `audits` — the rich metric source. A dict keyed by audit ID, with
  each entry carrying `id`, `title`, `description`, `score`,
  `scoreDisplayMode`, and — crucially for us — `numericValue` and
  `numericUnit`.
- `timing` — Lighthouse's own audit runtime (how long the tool took),
  not page metrics. Ignore for the parser.

### Which audits to emit as metrics

The parser should emit one Nyrkiö test-result dict with
`attributes["test_name"] = "homepage"` and one metric per headline
web-vital. Recommended audit IDs to pull from `audits[]`:

| Audit ID                    | Metric name  | `numericUnit` | direction         |
| --------------------------- | ------------ | ------------- | ----------------- |
| `first-contentful-paint`    | `fcp`        | `millisecond` | `lower_is_better` |
| `largest-contentful-paint`  | `lcp`        | `millisecond` | `lower_is_better` |
| `cumulative-layout-shift`   | `cls`        | `unitless`    | `lower_is_better` |
| `total-blocking-time`       | `tbt`        | `millisecond` | `lower_is_better` |
| `speed-index`               | `speed_index`| `millisecond` | `lower_is_better` |
| `interactive`               | `tti`        | `millisecond` | `lower_is_better` |
| `server-response-time`      | `server_response_time` | `millisecond` | `lower_is_better` |
| `total-byte-weight`         | `total_byte_weight`    | `byte`        | `lower_is_better` |

For each audit, `value` comes from `audits[id].numericValue` and
`unit` comes from `audits[id].numericUnit`. Lighthouse emits
`"millisecond"` as the unit for timings, `"unitless"` for CLS (it's a
score, not a duration), and `"byte"` for byte counts — map these to
`"ms"`, `""` (or `"unitless"`), and `"bytes"` respectively if the
parser wants shorter idiomatic names, but staying verbatim with
Lighthouse's strings is also fine and arguably more faithful.

The composite `categories.performance.score` (0..1) can additionally
be emitted as a metric named `performance_score` with
`direction: "higher_is_better"` and `unit: "score"`. It is the one
"higher is better" metric in the set — everything else is a latency or
weight that goes down when things improve.

### Ground-truth assertions

Unlike the canonical sample benchmark's tests 1–3, Lighthouse metrics
are **not** fixed quantities. LCP for this particular page will
depend on the runner's CPU, the Chrome version, and random scheduling
jitter. Parser tests for Lighthouse must therefore use **loose**
assertions — presence-of-key rather than numeric bounds:

- Assert `results[0]["attributes"]["test_name"] == "homepage"`.
- Assert `results[0]["timestamp"] == 0`.
- Assert the set of metric names includes `fcp`, `lcp`, `cls`, `tbt`,
  `speed_index`, `tti`, `server_response_time`, `total_byte_weight`
  (intersection, not exact equality — Lighthouse may add metrics in
  future versions and the parser should survive that).
- Assert each of those metrics has a numeric `value >= 0` and a
  non-empty `unit` string.
- Optionally assert `performance_score` is in `[0, 1]` if present.

This is weaker than the `2.0 < mean < 2.3` check we get from tests
1–3 in other frameworks — but it still verifies the parser is
actually reading the right fields, not just producing structurally
valid garbage.

### Failed audits

Lighthouse audits can report `score: null` or
`scoreDisplayMode: "notApplicable"` / `"error"` / `"informative"` for
individual metrics. If a metric the parser wanted is missing a
`numericValue`, the cleanest thing to do is skip it rather than emit
`value: null`. If the overall `runtimeError` key is present at the
top level of the report (Lighthouse couldn't complete the audit at
all), set `passed: false` on the result dict and still emit whatever
metrics did come through.

### Relationship to the fork

The predecessor TypeScript project at
[`nyrkio/change-detection`](https://github.com/nyrkio/change-detection)
did **not** have a Lighthouse parser. This is a clean-slate
implementation — no fixtures to crib, no prior art to align with.
