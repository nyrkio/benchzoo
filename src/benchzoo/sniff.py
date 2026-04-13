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

Each tier returns the detected framework name (matching the
:data:`benchzoo.parsers.PARSERS` registry keys) or ``None``.
"""

from __future__ import annotations

import json
import re


# Cap large-fixture parsing at ~1 MB. The signature check only needs
# the first few bytes / top-level keys; scanning a 50 MB file just to
# sniff is wasteful.
_SNIFF_BYTES = 1_048_576


def sniff(content: bytes | str) -> str | None:
    """Guess the framework that produced ``content``.

    Returns the framework name (matching :data:`PARSERS` keys) or
    ``None`` when the content is unrecognized or ambiguous.
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


# (framework, required substrings all appearing in the leading chunk)
# Order matters only when two signatures could both match the same
# input; each entry here is deliberately unique.
_JSON_SUBSTRING_SIGS: list[tuple[str, tuple[str, ...]]] = [
    ("pytest-benchmark", ('"machine_info"', '"commit_info"', '"benchmarks"')),
    ("google-benchmark", ('"context"', '"caches"', '"benchmarks"')),
    ("benchmarkdotnet",  ('"HostEnvironmentInfo"', '"Benchmarks"')),
    ("lighthouse",       ('"lighthouseVersion"', '"audits"')),
    ("k6",               ('"root_group"', '"metrics"')),
    ("memtier",          ('"ALL STATS"',)),
    ("asv",              ('"result_columns"', '"results"')),
    ("clickbench",       ('"system"', '"data_size"', '"result"')),
    ("playwright",       ('"suites"', '"stats"', '"expected"', '"config"')),
    ("mocha",            ('"stats"', '"tests"', '"pending"', '"passes"')),
    ("vitest-bench",     ('"files"', '"groups"', '"benchmarks"')),
    ("vegeta",           ('"latencies"', '"50th"', '"95th"', '"99th"')),
    ("hyperfine",        ('"results"', '"command"', '"exit_codes"')),
    ("benchmark-ips",    ('"benchmark_ips_version"',)),
    # Our self-labeled envelopes
    ("benchmark-js",     ('"framework": "benchmark.js"',)),
    ("tinybench",        ('"framework": "tinybench"',)),
    ("mitata",           ('"framework": "mitata"',)),
]


def _json_substring_signature(head: str) -> str | None:
    for framework, needles in _JSON_SUBSTRING_SIGS:
        if all(n in head for n in needles):
            return framework
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
                return "hyperfine"

        # Lighthouse: {"lighthouseVersion": ..., "audits": ...}
        if "lighthouseVersion" in keys and "audits" in keys:
            return "lighthouse"

        # Google Benchmark: {"context": {...}, "benchmarks": [...]}
        if "context" in keys and "benchmarks" in keys:
            ctx = doc.get("context")
            if isinstance(ctx, dict) and "caches" in ctx:
                return "google-benchmark"

        # BenchmarkDotNet: {"HostEnvironmentInfo": ..., "Benchmarks": ...}
        if "HostEnvironmentInfo" in keys and "Benchmarks" in keys:
            return "benchmarkdotnet"

        # pytest-benchmark: {"machine_info", "commit_info", "benchmarks"}
        if "machine_info" in keys and "benchmarks" in keys and "commit_info" in keys:
            return "pytest-benchmark"

        # k6 summary: {"root_group": ..., "metrics": {...}}
        if "root_group" in keys and "metrics" in keys:
            return "k6"

        # vegeta: has "latencies" top-level with "50th"/"95th"/"99th"
        if "latencies" in keys:
            lat = doc.get("latencies")
            if isinstance(lat, dict) and {"50th", "95th", "99th"} <= set(lat):
                return "vegeta"

        # memtier: has "ALL STATS" with the space in it
        if "ALL STATS" in keys:
            return "memtier"

        # asv: top-level has "result_columns" + "results"
        if "result_columns" in keys and "results" in keys:
            return "asv"

        # ClickBench: {"system", "result": [[...]]}
        if "system" in keys and "result" in keys and isinstance(doc.get("result"), list):
            first = (doc["result"] or [None])[0]
            if isinstance(first, list):
                return "clickbench"

        # Playwright: {"config": {...}, "suites": [...], "stats": {...}}
        if {"suites", "stats"} <= keys and isinstance(doc.get("suites"), list):
            stats = doc.get("stats", {})
            if isinstance(stats, dict) and "expected" in stats:
                return "playwright"

        # Mocha JSON: {"stats": {...}, "tests": [...], "pending": [...]}
        if {"stats", "tests", "pending", "passes"} <= keys:
            return "mocha"

        # Vitest bench: {"files": [{"groups": [{"benchmarks": ...}]}]}
        if "files" in keys and isinstance(doc.get("files"), list) and doc["files"]:
            f0 = doc["files"][0]
            if isinstance(f0, dict) and "groups" in f0:
                return "vitest-bench"

        # Our own emit-script envelopes (self-labeled)
        framework = doc.get("framework")
        if framework in {"benchmark.js", "tinybench", "mitata"}:
            return {
                "benchmark.js": "benchmark-js",
                "tinybench":    "tinybench",
                "mitata":       "mitata",
            }[framework]
        if framework == "benchzoo-custom-bigger-is-better":
            return "custom-json"
        if framework == "benchzoo-custom-smaller-is-better":
            return "custom-json"
        if framework == "benchmark_ips_version" in doc or "benchmark_ips_version" in doc:
            return "benchmark-ips"
        # benchmark-ips: signature is the version key at the top level
        if "benchmark_ips_version" in keys and "benchmarks" in keys:
            return "benchmark-ips"

    # Top-level array: benchzoo-owned custom JSON, or JMH results
    if isinstance(doc, list) and doc:
        first = doc[0]
        if isinstance(first, dict):
            # customBiggerIsBetter / customSmallerIsBetter — the ONLY
            # signal is the presence of {"name", "value"} with an
            # optional "unit"; can't distinguish the two variants from
            # content alone (that's a direction-interpretation choice,
            # not a shape choice). Return the umbrella name.
            if {"name", "value"} <= set(first) and all(
                isinstance(e, dict) and "name" in e and "value" in e for e in doc[:5]
            ):
                # Could be JMH (top-level array of benchmarks each with
                # "benchmark" + "primaryMetric"). Distinguish:
                if "primaryMetric" in first and "benchmark" in first:
                    return "jmh"
                # Otherwise custom-json.
                return "custom-json"

            # JMH: top-level array with "primaryMetric"
            if "primaryMetric" in first and "benchmark" in first:
                return "jmh"

        # Julia BenchmarkTools.jl: top-level array where [0] is
        # metadata dict with Julia/BenchmarkTools keys and [1] is
        # the tagged group.
        if len(doc) == 2 and isinstance(doc[0], dict):
            meta = doc[0]
            if "Julia" in meta and "BenchmarkTools" in meta:
                return "benchmarktools-jl"

    return None


def _sniff_ndjson_line(first: dict) -> str | None:
    """Detect ndjson streams by their first object's shape."""
    if not isinstance(first, dict):
        return None
    # k6 streaming: {"metric": ..., "type": "Metric" | "Point", "data": ...}
    if first.get("type") in {"Metric", "Point"} and "metric" in first and "data" in first:
        return "k6"
    # go test -json: {"Time": ..., "Action": ..., "Package": ...}
    if {"Action", "Package"} <= set(first):
        return "go-test-bench"
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
        return "catch2"
    if root == "phpbench":
        return "phpbench"
    if root == "TestRun" and "TeamTest" in attrs:
        # TRX: xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/..."
        return "dotnet-test"

    # For <testsuite> / <testsuites> roots the producer (jest /
    # gotestsum / Surefire / CTest / Catch2's junit reporter) is not
    # reliably distinguishable from the XML alone. pytest-benchmark's
    # junit is the one exception — its classnames use ".py::".
    # gotestsum emits byte-identical structure to vanilla junit, but
    # with a "TestX" name prefix the parser must strip — since we
    # can't tell that apart from a Java test class named ``TestX``,
    # we don't try. Everything else routes to junit-standard, whose
    # parser reads name + time verbatim.
    if root in {"testsuite", "testsuites"}:
        if ".py::" in stripped[:16384]:
            return "pytest-benchmark"
        return "junit-standard"

    return None


# ---------------------------------------------------------------------------
# Tier 3: CSV header signatures.
# ---------------------------------------------------------------------------

# First non-empty, non-comment line (stripped) → framework.
# These are exact matches; frameworks with header drift between
# versions are omitted (caller must specify framework explicitly).
_CSV_HEADERS = {
    'command,mean,stddev,median,user,system,min,max':
        "hyperfine",
    '"test","rps","avg_latency_ms","min_latency_ms","p50_latency_ms","p95_latency_ms","p99_latency_ms","max_latency_ms"':
        "redis-benchmark",
    'test_name,metric_name,unit,value,direction':
        "custom-csv",
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
            return "jmeter"
        # Locust stats CSV
        if line.startswith("Type,Name,Request Count,Failure Count,"):
            return "locust"
        # PerfStat CSV — comment block precedes real data, which
        # starts after "# started on ..." and is multi-line. Handle
        # in text tier instead.
        return None  # first non-empty line didn't match any header

    return None


# ---------------------------------------------------------------------------
# Tier 4: distinctive text substrings.
# ---------------------------------------------------------------------------

# Each entry: (framework, compiled pattern, description).
# Patterns are chosen to be unique — if one matches, we are
# confident. If several match, we return the first — so order
# matters: put more-specific patterns (wrk2 before wrk) first.
_TEXT_PATTERNS: list[tuple[str, "re.Pattern[str]"]] = [
    # wrk2's HdrHistogram label is its unique marker vs. plain wrk.
    ("wrk2",
     re.compile(r"^\s*Latency Distribution \(HdrHistogram", re.MULTILINE)),
    # wrk's banner line is distinct (and not also present in wrk2 —
    # wrk2 uses the same banner, so wrk's signature is wrk-specific
    # only when the wrk2 check above has failed).
    ("wrk",
     re.compile(r"^Running \d+(\.\d+)?s test @", re.MULTILINE)),
    # hey's Summary / Latency distribution lines
    ("hey",
     re.compile(r"^Summary:\n\s+Total:\s+[0-9.]+ secs", re.MULTILINE)),
    # perf stat headline
    ("perf-stat",
     re.compile(r"Performance counter stats for '")),
    # pgbench
    ("pgbench",
     re.compile(r"^transaction type:", re.MULTILINE)),
    # sysbench
    ("sysbench",
     re.compile(r"^sysbench \S+ \(using", re.MULTILINE)),
    # Bash builtin time: "real    Xm Y.ZZZs"
    ("time",
     re.compile(r"^real\s+\d+m\d+(\.\d+)?s\s*$\n^user\s+\d+m\d+",
                re.MULTILINE)),
    # GNU time -v
    ("time",
     re.compile(r"Elapsed \(wall clock\) time \(h:mm:ss or m:ss\):")),
    # JMH text output header
    ("jmh",
     re.compile(r"^Benchmark\s+Mode\s+Cnt\s+Score", re.MULTILINE)),
    # Catch2 v3 text banner
    ("catch2",
     re.compile(r"^All tests passed \(\d+ assertions? in \d+ test case",
                re.MULTILINE)),
    # Go test -bench text: "BenchmarkName-N  iterations  ns/op"
    # Distinguish from cargo bench text (same format) by package path
    # hint: go bench output contains "PASS" + "ok <package>"
    ("go-test-bench",
     re.compile(r"^Benchmark\S+-\d+\s+\d+\s+[\d,.]+\s+ns/op.*\n.*PASS",
                re.MULTILINE | re.DOTALL)),
    # cargo bench / libtest / criterion bencher — same line format
    # as go bench ns/op, but different prefix ("test NAME ... bench:")
    ("cargo-bench",
     re.compile(
         r"^test \S+ \.\.\. bench:\s+[\d,.]+\s+ns/iter \(\+/-",
         re.MULTILINE,
     )),
    # Gatling simulation.log
    ("gatling",
     re.compile(r"^RUN\t\S+\t\S+\t\d{13}\t", re.MULTILINE)),
    # mitata's pretty-table preamble precedes its JSON envelope;
    # when we have only the preamble (e.g. CI log capture), match
    # the "clk: ~X GHz" header banner that mitata prints unconditionally.
    ("mitata",
     re.compile(r"^clk: ~[\d.]+ (GHz|MHz)", re.MULTILINE)),
]


def _sniff_text(sample: str) -> str | None:
    for framework, pattern in _TEXT_PATTERNS:
        if pattern.search(sample):
            return framework
    return None
