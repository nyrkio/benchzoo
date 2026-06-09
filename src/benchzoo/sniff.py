"""Content-based framework detection.

Given raw benchmark output (as ``bytes`` or ``str``), :func:`sniff`
attempts to identify the framework that produced it by matching
against distinctive structural signatures.

**Hard invariant: the sniffer never returns a wrong answer.** When
the content is ambiguous or unrecognized, :func:`sniff` returns
``None`` and the caller is expected to fall through to an alternate
strategy (explicit framework selection from config, or the LLM
fallback parsers).

The signatures here capture easy, reliable cases only — about half
of benchzoo's 40+ frameworks. The other half tend to produce text
that overlaps too much with ad-hoc tool output to distinguish
reliably (bare numbers, generic tables). That's by design: the
sniffer is a phone book, not a search engine.

Detection strategy (tiers, tried in order, first match wins):

    1. JSON   — top-level keys or array-element shape.
    2. XML    — root element name, sometimes namespace.
    3. CSV    — literal first-line header.
    4. Text   — distinctive substring or regex that appears in one
                framework's output and nowhere else in our corpus.

Each tier returns ``"framework/format"`` — the framework name (a
:data:`benchzoo.parsers.PARSERS` key) plus the specific parser format
the matched representation maps to, e.g. ``"google-benchmark/json"`` or
``"k6/ndjson"``. This is directly splittable into
``find_parser(*result.split("/", 1))``. When the format genuinely can't
be determined from content alone (today only ``custom-json``'s
bigger/smaller direction, and a few text representations with no parser),
the bare framework name is returned and the caller must supply the
format. ``None`` means unrecognized or ambiguous.
"""

from __future__ import annotations

import json
import re


# Cap large-fixture parsing at ~1 MB. The signature check only needs
# the first few bytes / top-level keys; scanning a 50 MB file just to
# sniff is wasteful.
_SNIFF_BYTES = 1_048_576


def sniff(content: bytes | str) -> str | None:
    """Guess the framework and format that produced ``content``.

    Returns ``"framework/format"`` (e.g. ``"google-benchmark/json"``),
    splittable into ``find_parser(*result.split("/", 1))``. Returns a
    bare framework name when the format can't be inferred from content,
    or ``None`` when the content is unrecognized or ambiguous.
    """
    if isinstance(content, bytes):
        sample = content[:_SNIFF_BYTES].decode("utf-8", errors="replace")
    else:
        sample = content[:_SNIFF_BYTES]

    # Strip a leading UTF-8 BOM (dotnet TRX files ship with one).
    if sample.startswith("\ufeff"):
        sample = sample[1:]

    stripped = sample.lstrip()

    # Tier 1 — JSON
    if stripped.startswith(("{", "[")):
        result = _sniff_json(stripped)
        if result:
            return result

    # Tier 2 — XML
    if stripped.startswith("<"):
        result = _sniff_xml(stripped)
        if result:
            return result

    # Tier 3 — CSV (match the first non-empty line against known headers)
    result = _sniff_csv(sample)
    if result:
        return result

    # Tier 4 — distinctive text substrings
    result = _sniff_text(sample)
    if result:
        return result

    return None


# ---------------------------------------------------------------------------
# Tier 1: JSON signatures.
# ---------------------------------------------------------------------------


# (framework, format, required substrings all appearing in the leading chunk)
# Order matters only when two signatures could both match the same
# input; each entry here is deliberately unique. ``format`` is the
# PARSERS sub-key the matched representation maps to (k6's summary JSON
# vs its streaming ndjson are different parsers, so the format is part
# of the answer).
_JSON_SUBSTRING_SIGS: list[tuple[str, str, tuple[str, ...]]] = [
    ("pytest-benchmark", "json", ('"machine_info"', '"commit_info"', '"benchmarks"')),
    ("google-benchmark", "json", ('"context"', '"caches"', '"benchmarks"')),
    ("benchmarkdotnet",  "json", ('"HostEnvironmentInfo"', '"Benchmarks"')),
    ("lighthouse",       "json", ('"lighthouseVersion"', '"audits"')),
    ("k6",               "summary", ('"root_group"', '"metrics"')),
    ("memtier",          "json", ('"ALL STATS"',)),
    ("asv",              "json", ('"result_columns"', '"results"')),
    ("clickbench",       "json", ('"system"', '"data_size"', '"result"')),
    ("playwright",       "json", ('"suites"', '"stats"', '"expected"', '"config"')),
    ("mocha",            "json", ('"stats"', '"tests"', '"pending"', '"passes"')),
    ("vitest-bench",     "json", ('"files"', '"groups"', '"benchmarks"')),
    ("vegeta",           "json", ('"latencies"', '"50th"', '"95th"', '"99th"')),
    ("hyperfine",        "json", ('"results"', '"command"', '"exit_codes"')),
    ("benchmark-ips",    "json", ('"benchmark_ips_version"',)),
    # Our self-labeled envelopes
    ("benchmark-js",     "json", ('"framework": "benchmark.js"',)),
    ("tinybench",        "json", ('"framework": "tinybench"',)),
    ("mitata",           "json", ('"framework": "mitata"',)),
]


def _json_substring_signature(head: str) -> str | None:
    for framework, fmt, needles in _JSON_SUBSTRING_SIGS:
        if all(n in head for n in needles):
            return f"{framework}/{fmt}"
    return None


def _sniff_json(stripped: str) -> str | None:
    # We look for top-level-key substrings first — works even when
    # the full buffer is a multi-MB fixture (pytest-benchmark
    # regularly hits 2–5 MB) that doesn't fit in our 1 MB sample
    # window. Substring matching against the leading bytes is also
    # cheaper than a full json.loads.
    head = stripped[:8192]
    sig = _json_substring_signature(head)
    if sig:
        return sig

    # Fall back to a full parse for cases that genuinely need the
    # tree (array-of-objects shapes, nested key checks).
    try:
        doc = json.loads(stripped)
    except json.JSONDecodeError:
        # Might be ndjson (one JSON object per line). Peek at the
        # first line only.
        first_line, _, _ = stripped.partition("\n")
        try:
            first = json.loads(first_line)
        except json.JSONDecodeError:
            return None
        return _sniff_ndjson_line(first)

    # Top-level object shapes
    if isinstance(doc, dict):
        keys = set(doc)
        # hyperfine: {"results": [{"command": ..., "mean": ...}]}
        if "results" in keys and isinstance(doc.get("results"), list) and doc["results"]:
            first = doc["results"][0]
            if isinstance(first, dict) and "command" in first and "mean" in first and "stddev" in first:
                return "hyperfine/json"

        # Lighthouse: {"lighthouseVersion": ..., "audits": ...}
        if "lighthouseVersion" in keys and "audits" in keys:
            return "lighthouse/json"

        # Google Benchmark: {"context": {...}, "benchmarks": [...]}
        if "context" in keys and "benchmarks" in keys:
            ctx = doc.get("context")
            if isinstance(ctx, dict) and "caches" in ctx:
                return "google-benchmark/json"

        # BenchmarkDotNet: {"HostEnvironmentInfo": ..., "Benchmarks": ...}
        if "HostEnvironmentInfo" in keys and "Benchmarks" in keys:
            return "benchmarkdotnet/json"

        # pytest-benchmark: {"machine_info", "commit_info", "benchmarks"}
        if "machine_info" in keys and "benchmarks" in keys and "commit_info" in keys:
            return "pytest-benchmark/json"

        # k6 summary: {"root_group": ..., "metrics": {...}}
        if "root_group" in keys and "metrics" in keys:
            return "k6/summary"

        # vegeta: has "latencies" top-level with "50th"/"95th"/"99th"
        if "latencies" in keys:
            lat = doc.get("latencies")
            if isinstance(lat, dict) and {"50th", "95th", "99th"} <= set(lat):
                return "vegeta/json"

        # memtier: has "ALL STATS" with the space in it
        if "ALL STATS" in keys:
            return "memtier/json"

        # asv: top-level has "result_columns" + "results"
        if "result_columns" in keys and "results" in keys:
            return "asv/json"

        # ClickBench: {"system", "result": [[...]]}
        if "system" in keys and "result" in keys and isinstance(doc.get("result"), list):
            first = (doc["result"] or [None])[0]
            if isinstance(first, list):
                return "clickbench/json"

        # Playwright: {"config": {...}, "suites": [...], "stats": {...}}
        if {"suites", "stats"} <= keys and isinstance(doc.get("suites"), list):
            stats = doc.get("stats", {})
            if isinstance(stats, dict) and "expected" in stats:
                return "playwright/json"

        # Mocha JSON: {"stats": {...}, "tests": [...], "pending": [...]}
        if {"stats", "tests", "pending", "passes"} <= keys:
            return "mocha/json"

        # Vitest bench: {"files": [{"groups": [{"benchmarks": ...}]}]}
        if "files" in keys and isinstance(doc.get("files"), list) and doc["files"]:
            f0 = doc["files"][0]
            if isinstance(f0, dict) and "groups" in f0:
                return "vitest-bench/json"

        # Our own emit-script envelopes (self-labeled)
        framework = doc.get("framework")
        if framework in {"benchmark.js", "tinybench", "mitata"}:
            return {
                "benchmark.js": "benchmark-js/json",
                "tinybench":    "tinybench/json",
                "mitata":       "mitata/json",
            }[framework]
        # The custom-json envelope self-labels its direction, so here —
        # unlike the bare-array form below — we CAN name the format.
        if framework == "benchzoo-custom-bigger-is-better":
            return "custom-json/bigger_is_better"
        if framework == "benchzoo-custom-smaller-is-better":
            return "custom-json/smaller_is_better"
        if framework == "benchmark_ips_version" in doc or "benchmark_ips_version" in doc:
            return "benchmark-ips/json"
        # benchmark-ips: signature is the version key at the top level
        if "benchmark_ips_version" in keys and "benchmarks" in keys:
            return "benchmark-ips/json"

    # Top-level array: benchzoo-owned custom JSON, or JMH results
    if isinstance(doc, list) and doc:
        first = doc[0]
        if isinstance(first, dict):
            # Nyrkiö's historical JSON format — same per-object shape
            # the ndjson sniff catches, but in array form.
            if _looks_like_nyrkio_v1_row(first):
                return "nyrkio-json/v1"

            # customBiggerIsBetter / customSmallerIsBetter — the ONLY
            # signal is the presence of {"name", "value"} with an
            # optional "unit"; can't distinguish the two variants from
            # content alone (that's a direction-interpretation choice,
            # not a shape choice). Return the bare framework name with no
            # format — the caller must supply bigger_is_better /
            # smaller_is_better itself.
            if {"name", "value"} <= set(first) and all(
                isinstance(e, dict) and "name" in e and "value" in e for e in doc[:5]
            ):
                # Could be JMH (top-level array of benchmarks each with
                # "benchmark" + "primaryMetric"). Distinguish:
                if "primaryMetric" in first and "benchmark" in first:
                    return "jmh/json"
                # Otherwise custom-json, format-ambiguous (no "/format").
                return "custom-json"

            # JMH: top-level array with "primaryMetric"
            if "primaryMetric" in first and "benchmark" in first:
                return "jmh/json"

        # Julia BenchmarkTools.jl: top-level array where [0] is
        # metadata dict with Julia/BenchmarkTools keys and [1] is
        # the tagged group.
        if len(doc) == 2 and isinstance(doc[0], dict):
            meta = doc[0]
            if "Julia" in meta and "BenchmarkTools" in meta:
                return "benchmarktools-jl/json"

    return None


def _looks_like_nyrkio_v1_row(obj: dict) -> bool:
    """Shape check shared by the array and ndjson paths.

    A Nyrkiö-v1 row is a flat dict with ``timestamp`` (epoch seconds,
    not a wall-clock string), a ``metrics`` list, and an
    ``attributes`` dict that carries git provenance inline —
    specifically ``git_repo`` (a URL) and ``git_commit``. The combined
    presence of those three keys is distinctive enough; no modern
    framework emits git keys in its own output.
    """
    if not isinstance(obj, dict):
        return False
    if not isinstance(obj.get("timestamp"), (int, float)):
        return False
    metrics = obj.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        return False
    attrs = obj.get("attributes")
    if not isinstance(attrs, dict):
        return False
    if "git_repo" not in attrs or "git_commit" not in attrs:
        return False
    return True


def _sniff_ndjson_line(first: dict) -> str | None:
    """Detect ndjson streams by their first object's shape."""
    if not isinstance(first, dict):
        return None
    # k6 streaming: {"metric": ..., "type": "Metric" | "Point", "data": ...}
    if first.get("type") in {"Metric", "Point"} and "metric" in first and "data" in first:
        return "k6/ndjson"
    # go test -json: {"Time": ..., "Action": ..., "Package": ...}
    if {"Action", "Package"} <= set(first):
        return "go-test-bench/json"
    # Nyrkiö-v1 ndjson (tigerbeetle/devhubdb style).
    if _looks_like_nyrkio_v1_row(first):
        return "nyrkio-json/v1"
    return None


# ---------------------------------------------------------------------------
# Tier 2: XML signatures.
# ---------------------------------------------------------------------------

# Match opening tag of root (after optional <?xml ...?> preamble and
# any whitespace / comments we don't care about). We accept an
# optional namespace attribute.
_XML_ROOT_RE = re.compile(
    r"(?:<\?xml[^>]*\?>\s*)?(?:<!--.*?-->\s*)*<([a-zA-Z_][\w:-]*)\b([^>]*)",
    re.DOTALL,
)


def _sniff_xml(stripped: str) -> str | None:
    m = _XML_ROOT_RE.match(stripped)
    if not m:
        return None
    root, attrs = m.group(1), m.group(2) or ""

    if root == "Catch2TestRun":
        return "catch2/xml"
    if root == "phpbench":
        return "phpbench/xml"
    if root == "TestRun" and "TeamTest" in attrs:
        # TRX: xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/..."
        return "dotnet-test/trx"

    # For <testsuite> / <testsuites> roots we look for producer
    # fingerprints inside the document:
    #   - pytest-benchmark uses ".py::" in its classnames.
    #   - gotestsum embeds a <property name="go.version" ...> in every
    #     junit it writes — a rock-solid go signal (no Java/jest/
    #     ctest/catch2 junit carries that key).
    # Everything else routes to junit-standard, whose parser reads
    # name + time verbatim.
    if root in {"testsuite", "testsuites"}:
        head = stripped[:16384]
        if ".py::" in head:
            return "pytest-benchmark/junit"
        if 'name="go.version"' in head:
            return "junit-go/xml"
        return "junit-standard/xml"

    return None


# ---------------------------------------------------------------------------
# Tier 3: CSV header signatures.
# ---------------------------------------------------------------------------

# First non-empty, non-comment line (stripped) → framework.
# These are exact matches; frameworks with header drift between
# versions are omitted (caller must specify framework explicitly).
_CSV_HEADERS = {
    'command,mean,stddev,median,user,system,min,max':
        "hyperfine/csv",
    '"test","rps","avg_latency_ms","min_latency_ms","p50_latency_ms","p95_latency_ms","p99_latency_ms","max_latency_ms"':
        "redis-benchmark/csv",
    'test_name,metric_name,unit,value,direction':
        "custom-csv/csv",
}


def _sniff_csv(sample: str) -> str | None:
    for raw in sample.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line in _CSV_HEADERS:
            return _CSV_HEADERS[line]

        # JMeter's per-sample CSV
        if line.startswith("timeStamp,elapsed,label,responseCode,"):
            return "jmeter/csv"
        # Locust stats CSV
        if line.startswith("Type,Name,Request Count,Failure Count,"):
            return "locust/csv"
        # PerfStat CSV — comment block precedes real data, which
        # starts after "# started on ..." and is multi-line. Handle
        # in text tier instead.
        return None  # first non-empty line didn't match any header

    return None


# ---------------------------------------------------------------------------
# Tier 4: distinctive text substrings.
# ---------------------------------------------------------------------------

# Each entry: (framework, format, compiled pattern). ``format`` is the
# PARSERS sub-key the matched text maps to, or ``None`` when the
# framework has no parser for this text representation (jmh/catch2 only
# parse their structured output; mitata only parses JSON) — in that case
# sniff names the framework but leaves the format for the caller, so
# find_parser falls through rather than mis-dispatching.
# Patterns are chosen to be unique — if one matches, we are confident.
# If several match, we return the first — so order matters: put
# more-specific patterns (wrk2 before wrk) first.
_TEXT_PATTERNS: list[tuple[str, str | None, "re.Pattern[str]"]] = [
    # wrk2's HdrHistogram label is its unique marker vs. plain wrk.
    ("wrk2", "text",
     re.compile(r"^\s*Latency Distribution \(HdrHistogram", re.MULTILINE)),
    # wrk's banner line is distinct (and not also present in wrk2 —
    # wrk2 uses the same banner, so wrk's signature is wrk-specific
    # only when the wrk2 check above has failed).
    ("wrk", "text",
     re.compile(r"^Running \d+(\.\d+)?s test @", re.MULTILINE)),
    # hey's Summary / Latency distribution lines
    ("hey", "text",
     re.compile(r"^Summary:\n\s+Total:\s+[0-9.]+ secs", re.MULTILINE)),
    # perf stat headline
    ("perf-stat", "text",
     re.compile(r"Performance counter stats for '")),
    # pgbench
    ("pgbench", "text",
     re.compile(r"^transaction type:", re.MULTILINE)),
    # sysbench
    ("sysbench", "text",
     re.compile(r"^sysbench \S+ \(using", re.MULTILINE)),
    # Bash builtin time: "real    Xm Y.ZZZs"
    ("time", "builtin",
     re.compile(r"^real\s+\d+m\d+(\.\d+)?s\s*$\n^user\s+\d+m\d+",
                re.MULTILINE)),
    # GNU time -v
    ("time", "gnu",
     re.compile(r"Elapsed \(wall clock\) time \(h:mm:ss or m:ss\):")),
    # JMH summary-table header → jmh_text (timestamp-tolerant for CI logs).
    ("jmh", "text",
     re.compile(r"^\s*(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+)?"
                r"Benchmark\s+Mode\s+Cnt\s+Score\s+Error\s+Units\s*$",
                re.MULTILINE)),
    # Catch2 benchmark table header → catch2_text.
    ("catch2", "text",
     re.compile(r"^.*benchmark name\s+samples\s+iterations\s+est run time\s*$",
                re.MULTILINE)),
    # Go test -bench text: "BenchmarkName-N  iterations  ns/op"
    # Distinguish from cargo bench text (same format) by package path
    # hint: go bench output contains "PASS" + "ok <package>"
    ("go-test-bench", "text",
     re.compile(r"^Benchmark\S+-\d+\s+\d+\s+[\d,.]+\s+ns/op.*\n.*PASS",
                re.MULTILINE | re.DOTALL)),
    # cargo bench / libtest / criterion bencher — same line format
    # as go bench ns/op, but different prefix ("test NAME ... bench:")
    ("cargo-bench", "text",
     re.compile(
         r"^test \S+ \.\.\. bench:\s+[\d,.]+\s+ns/iter \(\+/-",
         re.MULTILINE,
     )),
    # criterion's DEFAULT stdout: a "time:  [lo <u> mid <u> hi <u>]"
    # confidence-interval line. Distinctive (three time-unit values in
    # brackets) so it's found even buried in a wall of cargo-compile
    # output — unlike the bencher format above, which criterion only
    # emits with --output-format bencher.
    ("criterion", "text",
     re.compile(
         r"^\s*time:\s+\[\s*[0-9.]+\s*(?:ns|µs|μs|us|ms|s)\s+"
         r"[0-9.]+\s*(?:ns|µs|μs|us|ms|s)\s+"
         r"[0-9.]+\s*(?:ns|µs|μs|us|ms|s)\s*\]",
         re.MULTILINE,
     )),
    # linetimer (PyPI ``linetimer``) CodeTimer stdout: one line per timed
    # block, "Code block 'NAME' took: 1.50120 s". Used e.g. by
    # pola-rs/polars-benchmark's TPC-H suite; usually buried in a CI log.
    ("linetimer", "text",
     re.compile(
         r"^\s*(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+)?"
         r"Code block '[^']*' took:\s+[0-9.]+(?:[eE][+-]?[0-9]+)?\s*"
         r"(?:ns|µs|μs|us|ms|sec|s|min|m|h)\b",
         re.MULTILINE,
     )),
    # Gatling simulation.log
    ("gatling", "log",
     re.compile(r"^RUN\t\S+\t\S+\t\d{13}\t", re.MULTILINE)),
    # mitata's pretty-table header → mitata_text (its "json" artifact is
    # really ANSI console text, so the text parser is the real one).
    ("mitata", "text",
     re.compile(r"^(?:\d{4}-\d\d-\d\dT[\d:.]+Z\s)?benchmark\s+avg \(min … max\) p75 / p99",
                re.MULTILINE)),
    ("benchmarkdotnet", "text", re.compile(r"^(?:\S+\s)?BenchmarkDotNet v\d", re.MULTILINE)),
    ("pytest-benchmark", "text", re.compile(r"^\s*(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+)?Name \(time in (?:ns|µs|μs|us|ms|s)\)\s+Min\s+Max\s+Mean\s+StdDev\b", re.MULTILINE)),
    ("hyperfine", "text", re.compile(r"^.*Time\s*\(mean\s*[±+].*\):\s*[0-9.]+\s*(?:ns|µs|μs|us|ms|s)\s*[±+]", re.MULTILINE)),
    ("asv", "text", re.compile(r"^.*?·\s*Running \d+ total benchmarks \(\d+ commits?", re.MULTILINE)),
    ("benchmark-ips", "text", re.compile(r"\(±\s*[0-9.]+%\)\s*i/s\s+\(\s*[0-9.]+\s*(?:ns|µs|μs|us|ms|s)/i\s*\)")),
    ("vitest-bench", "text", re.compile(r"^\s*(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+)?(?:\x1b\[[0-9;]*m)*Benchmarking is an experimental feature\.", re.MULTILINE)),
    ("benchmarktools-jl", "text", re.compile(r"\bTrial\(\s*[0-9][0-9.]*\s*(?:ns|µs|μs|us|ms|s)\s*\)", re.MULTILINE)),
    ("phpbench", "text", re.compile(r"^\s*(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+)?\|\s*benchmark\s+\|\s*subject\s+\|\s*set\s+\|\s*revs\s+\|\s*its\s+\|\s*mem_peak\s+\|\s*mode\s+\|\s*rstdev\s+\|", re.MULTILINE)),
    ("locust", "text", re.compile(r"^(?:\d{4}-\d{2}-\d{2}T[\d:.]+Z\s+)?Type\s+Name\s+# reqs\s+# fails", re.MULTILINE)),
    ("jmeter", "text", re.compile(r"summary\s*=\s*\d+ in \d{2}:\d{2}:\d{2} = [0-9.]+/s Avg:\s*\d+ Min:\s*\d+ Max:\s*\d+ Err:", re.MULTILINE)),
    ("redis-benchmark", "text", re.compile(r"^\s*(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+)?throughput summary:\s+[0-9.]+\s+requests per second", re.MULTILINE)),
    ("memtier", "text", re.compile(r"^\s*(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+)?Type\s+Ops/sec\s+Hits/sec\s+Misses/sec\b", re.MULTILINE)),
    ("junit-jest", "text", re.compile(r"^(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+)?\s*[✓√]\s+\S.*\(\d+(?:\.\d+)?\s*(?:ms|s|min)\)\s*$", re.MULTILINE)),
    ("junit-go", "text", re.compile(r"^\s*(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+)?---\s+(?:PASS|FAIL):\s+Test\S*\s+\([0-9.]+s\)", re.MULTILINE)),
    ("ctest", "text", re.compile(r"^\s*(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+)?\d+/\d+\s+Test\s+#\d+:\s+\S.*?\s+\.{2,}\s*(?:\*{3}\s*)?\w[\w ]*?\s+[0-9]+(?:\.[0-9]+)?\s+sec\b", re.MULTILINE)),
]


def _sniff_text(sample: str) -> str | None:
    for framework, fmt, pattern in _TEXT_PATTERNS:
        if pattern.search(sample):
            return f"{framework}/{fmt}" if fmt else framework
    return None
