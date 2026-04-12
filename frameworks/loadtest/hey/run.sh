#!/bin/bash
# Run a hey load test against a local nginx instance and write the
# text output to ./output.txt. This is the command the workflow (and
# a local `act` run) execute; keeping it in a script rather than
# inline in the YAML makes it easy to iterate locally.
#
# hey fundamentally measures real HTTP request/response latency; it
# needs an HTTP target to talk to. We stand up nginx in the foreground
# serving the sibling index.html on port 8080, run hey against it,
# then `trap` a kill so nginx goes away on any exit (success, error,
# or Ctrl-C).
#
# hey flags:
#   -z 5s  — 5 second test duration. Short enough to keep CI minutes
#            cheap, long enough for the latency histogram and
#            percentile distribution to settle. This is hey's default
#            duration behavior when using `-z` instead of `-n`.
#   -c 10  — 10 concurrent workers (open HTTP connections). This is
#            also hey's built-in default; we pass it explicitly so the
#            command line documents the intended load rather than
#            relying on upstream defaults that could shift.
#
# hey has no JSON or CSV output mode — its only output is the text
# report it prints at the end of a run. We capture both stdout and
# stderr into output.txt — hey writes its report to stdout but error
# messages (e.g. "connection refused") go to stderr, and the parser
# sees whatever landed in the artifact.
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

# Give nginx a beat to bind before hey connects.
for _ in 1 2 3 4 5 6 7 8 9 10; do
    if curl -sSf http://localhost:8080/ >/dev/null 2>&1; then
        break
    fi
    sleep 0.2
done

hey -z 5s -c 10 http://localhost:8080/ > output.txt 2>&1
