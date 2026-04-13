#!/bin/bash
# Run an Apache JMeter load test against a local nginx instance and
# write the CSV results to ./output.csv. This is the command the
# workflow (and a local `act` run) execute; keeping it in a script
# rather than inline in the YAML makes it easy to iterate locally.
#
# JMeter fundamentally measures real HTTP request/response latency; it
# needs an HTTP target to talk to. We stand up nginx in the foreground
# serving the sibling index.html on port 8080, run JMeter against it
# in non-GUI mode, then `trap` a kill so nginx goes away on any exit
# (success, error, or Ctrl-C).
#
# JMeter flags:
#   -n             — non-GUI ("command-line") mode. Required for CI;
#                    without this JMeter tries to open its Swing UI.
#   -t test-plan.jmx — the JMX test plan to execute.
#   -l output.csv  — write the per-sample results log to this file.
#                    Defaults to CSV based on JMeter's
#                    jmeter.save.saveservice.output_format property
#                    (CSV in the stock install).
#   -j jmeter.log  — JMeter's own run log (not sample results). Useful
#                    for debugging CI failures.
set -euo pipefail

cd "$(dirname "$0")"

# Clean up any stale nginx state from a previous local run. The
# workflow starts from a fresh checkout so this is only relevant for
# repeated local `./run.sh` invocations.
rm -rf client_body_temp proxy_temp fastcgi_temp uwsgi_temp scgi_temp
rm -f  nginx.pid nginx-error.log output.csv jmeter.log

nginx -p "$(pwd)" -c nginx.conf &
NGINX_PID=$!
trap 'kill "${NGINX_PID}" 2>/dev/null || true' EXIT

# Give nginx a beat to bind before JMeter connects.
for _ in 1 2 3 4 5 6 7 8 9 10; do
    if curl -sSf http://localhost:8080/ >/dev/null 2>&1; then
        break
    fi
    sleep 0.2
done

jmeter -n -t test-plan.jmx -l output.csv -j jmeter.log
