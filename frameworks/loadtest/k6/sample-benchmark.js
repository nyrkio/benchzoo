// k6 implementation of the benchzoo canonical sample benchmark
// (see docs/sample-benchmark.md).
//
// NOTE — synthetic, non-HTTP adaptation:
//
// k6 is a load-test runner: in normal use it issues HTTP (or gRPC,
// WebSocket, ...) requests against a target and reports per-request
// latency percentiles, throughput, and error counts. The canonical
// sample benchmark (sleep / tight CPU loop / small write / monthly
// sleep) does not fit that shape at all — none of the four tests are
// HTTP, and test 3 wants a filesystem write which k6's sandboxed JS
// runtime does not permit.
//
// Rather than stand up an nginx container and invent four HTTP
// endpoints, we exercise k6's output format directly by recording
// per-test durations into custom `Trend` metrics from inside the VU
// script. The script runs exactly once (1 VU, 1 iteration) and emits
// one data point per custom Trend. That is enough to produce a
// representative `summary.json` and streaming `output.json` for parser
// development.
//
// A future, "real k6" framework entry could benchmark HTTP against an
// nginx service container and report actual request latencies; that is
// a separate concern and does not block parser work on the output
// format.

import { Trend } from 'k6/metrics';
import { sleep } from 'k6';

// `true` marks these as time metrics (unit: ms). k6's summary will
// then format them with ms-appropriate stats.
const benchmark1Trend = new Trend('benchmark1', true);
const benchmark2Trend = new Trend('benchmark2', true);
const benchmark3Trend = new Trend('benchmark3', true);
const benchmark4Trend = new Trend('benchmark4', true);

export const options = {
  vus: 1,
  iterations: 1,
};

export default function () {
  // ---------------------------------------------------------------
  // benchmark1 — sleep 2.15 s. Uses Date.now() for consistency
  // with the other tests; millisecond resolution is plenty here.
  // ---------------------------------------------------------------
  {
    const t0 = Date.now();
    sleep(2.15);
    benchmark1Trend.add(Date.now() - t0);
  }

  // ---------------------------------------------------------------
  // benchmark2 — tight loop 0..1000, summing into a sink so the JS
  // engine (goja) cannot elide it. k6's goja runtime does NOT expose
  // the W3C `performance.now()` global, so we use `Date.now()` with
  // millisecond resolution. Test 2's body is sub-millisecond and will
  // typically record 0 ms — that is fine: the purpose is to exercise
  // the parser's handling of small / zero-valued durations, not to
  // produce a stable number.
  // ---------------------------------------------------------------
  {
    const t0 = Date.now();
    let sum = 0;
    for (let i = 0; i < 1000; i++) sum += i;
    // Touch `sum` so the loop is observably side-effecting.
    if (sum < 0) throw new Error('unreachable');
    benchmark2Trend.add(Date.now() - t0);
  }

  // ---------------------------------------------------------------
  // benchmark3 — "write 1.4 MB to /dev/null". k6 scripts run inside a
  // sandboxed JS runtime with no filesystem write access, so there is
  // no /dev/null to write to. Instead, allocate a 1.4 MB ArrayBuffer
  // and sparsely fill it — this exercises an allocation + memory-touch
  // operation of roughly the right magnitude. The measurement
  // therefore represents "allocate and touch 1.4 MB of memory", not
  // disk I/O. This is documented in the README.
  // ---------------------------------------------------------------
  {
    const t0 = Date.now();
    const buf = new ArrayBuffer(1_400_000);
    const view = new Uint8Array(buf);
    for (let i = 0; i < view.length; i += 4096) {
      view[i] = i & 0xff;
    }
    benchmark3Trend.add(Date.now() - t0);
  }

  // ---------------------------------------------------------------
  // benchmark4 — monthly change-point showcase. Sleep duration is
  // 2.15 + ((UTC month mod 3) - 1), so the series cycles through
  // {1.15, 2.15, 3.15} seconds with period 3 months. See test 4 in
  // docs/sample-benchmark.md.
  // ---------------------------------------------------------------
  {
    const m = new Date().getUTCMonth() + 1; // 1..12
    const sleepSeconds = 2.15 + ((m % 3) - 1);
    const t0 = Date.now();
    sleep(sleepSeconds);
    benchmark4Trend.add(Date.now() - t0);
  }
}
