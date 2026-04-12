#!/bin/bash
# Run a vegeta attack against a local nginx instance and write the
# results (both JSON and text reports, plus a histogram) to this
# directory. This is the command the workflow (and a local `act` run)
# execute; keeping it in a script rather than inline in the YAML makes
# it easy to iterate locally.
#
# vegeta, like wrk, fundamentally measures real HTTP request/response
# latency; it needs an HTTP target to talk to. We stand up nginx in
# the foreground serving the sibling index.html on port 8080, attack
# it, then `trap` a kill so nginx goes away on any exit (success,
# error, or Ctrl-C).
#
# vegeta flags:
#   attack -duration=5s  — 5 second attack duration. Short enough to
#                          keep CI minutes cheap, long enough for the
#                          latency distribution to settle.
#   -rate=100/s          — constant 100 requests/sec. Gentle enough
#                          that nginx on a shared runner should have
#                          no trouble; loaded enough to produce a real
#                          distribution over 5 seconds (500 samples).
#   -targets=targets.txt — one target: GET http://localhost:8080/.
#
# The raw binary `results.bin` is then reduced three ways via
# `vegeta report`:
#   - type=json  → output.json       (the primary machine-readable
#                                     format; the parser's target)
#   - (default)  → output.txt        (human-readable text report;
#                                     fallback parser format and
#                                     easy to eyeball in artifact UI)
#   - type=hist  → output-histogram.txt (bucketed histogram across
#                                        a handful of latency ranges)
set -euo pipefail

cd "$(dirname "$0")"

# Clean up any stale nginx state from a previous local run. The
# workflow starts from a fresh checkout so this is only relevant for
# repeated local `./run.sh` invocations.
rm -rf client_body_temp proxy_temp fastcgi_temp uwsgi_temp scgi_temp
rm -f  nginx.pid nginx-error.log results.bin

nginx -p "$(pwd)" -c nginx.conf &
NGINX_PID=$!
trap 'kill "${NGINX_PID}" 2>/dev/null || true' EXIT

# Give nginx a beat to bind before vegeta connects.
for _ in 1 2 3 4 5 6 7 8 9 10; do
    if curl -sSf http://localhost:8080/ >/dev/null 2>&1; then
        break
    fi
    sleep 0.2
done

vegeta attack -duration=5s -rate=100/s -targets=targets.txt > results.bin

vegeta report -type=json results.bin > output.json
vegeta report results.bin > output.txt
vegeta report -type=hist '[0,10ms,50ms,100ms,500ms]' results.bin > output-histogram.txt
