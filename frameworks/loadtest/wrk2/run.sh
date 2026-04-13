#!/bin/bash
# Run a wrk2 constant-throughput load test against a local nginx
# instance and write the text output to ./output.txt.
#
# wrk2 is Gil Tene's fork of wrk that adds (a) a `-R<rate>`
# constant-throughput mode that corrects for coordinated omission and
# (b) HDR histogram output with extended percentiles (p99.9, p99.99,
# p99.999, p99.9999, p100). The text report is a superset of wrk's —
# all of wrk's fields still appear in the same format — so a parser
# can largely reuse wrk's regex logic and just handle the extra
# percentile rows.
#
# We install wrk2 as `/usr/local/bin/wrk2` (see workflow) rather than
# shadowing the system `wrk` binary, to make it obvious which tool is
# being invoked.
#
# wrk2 flags:
#   -t2       — 2 threads.
#   -c10      — 10 open HTTP connections.
#   -d5s      — 5 second test duration.
#   -R1000    — constant 1000 req/s target throughput. Low enough that
#               nginx on a shared CI runner won't saturate, so the
#               measured latencies reflect the stack's behavior at a
#               sustainable rate rather than under overload. wrk2
#               requires this flag — without it the tool exits with a
#               usage error.
#   --latency — print the HDR-histogram-derived "Latency Distribution
#               (HdrHistogram - Recorded Latency)" section with
#               percentiles all the way to p99.9999 / p100. We do not
#               pass --latency-percentiles (the full detailed spectrum)
#               to keep the captured output small.
set -euo pipefail

cd "$(dirname "$0")"

rm -rf client_body_temp proxy_temp fastcgi_temp uwsgi_temp scgi_temp
rm -f  nginx.pid nginx-error.log

nginx -p "$(pwd)" -c nginx.conf &
NGINX_PID=$!
trap 'kill "${NGINX_PID}" 2>/dev/null || true' EXIT

for _ in 1 2 3 4 5 6 7 8 9 10; do
    if curl -sSf http://localhost:8080/ >/dev/null 2>&1; then
        break
    fi
    sleep 0.2
done

wrk2 -t2 -c10 -d5s -R1000 --latency http://localhost:8080/ > output.txt 2>&1
