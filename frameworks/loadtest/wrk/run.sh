#!/bin/bash
# Run a wrk load test against a local nginx instance and write the
# text output to ./output.txt. This is the command the workflow (and a
# local `act` run) execute; keeping it in a script rather than inline
# in the YAML makes it easy to iterate locally.
#
# wrk fundamentally measures real HTTP request/response latency; it
# needs an HTTP target to talk to. We stand up nginx in the foreground
# serving the sibling index.html on port 8080, run wrk against it,
# then `trap` a kill so nginx goes away on any exit (success, error,
# or Ctrl-C).
#
# wrk flags:
#   -t2    — 2 threads. More threads wouldn't hurt on a multi-core
#            runner but 2 is plenty to saturate a single nginx worker
#            over the loopback.
#   -c10   — 10 open HTTP connections.
#   -d5s   — 5 second test duration. Short enough to keep CI minutes
#            cheap, long enough for wrk's latency histogram to settle.
#   --latency — print the per-percentile latency distribution
#               ("Latency Distribution", p50/p75/p90/p99) in addition
#               to the default summary. That table is the richest
#               parser-facing payload wrk produces.
#
# We capture both stdout and stderr into output.txt — wrk writes its
# report to stdout but some error messages go to stderr, and the
# parser sees whatever landed in the artifact.
set -euo pipefail

cd "$(dirname "$0")"

# Clean up any stale nginx state from a previous local run. The
# workflow starts from a fresh checkout so this is only relevant for
# repeated local `./run.sh` invocations.
rm -rf client_body_temp proxy_temp fastcgi_temp uwsgi_temp scgi_temp
rm -f  nginx.pid nginx-error.log

nginx -p "$(pwd)" -c nginx.conf &
NGINX_PID=$!
trap 'kill "${NGINX_PID}" 2>/dev/null || true' EXIT

# Give nginx a beat to bind before wrk connects.
for _ in 1 2 3 4 5 6 7 8 9 10; do
    if curl -sSf http://localhost:8080/ >/dev/null 2>&1; then
        break
    fi
    sleep 0.2
done

wrk -t2 -c10 -d5s --latency http://localhost:8080/ > output.txt 2>&1
