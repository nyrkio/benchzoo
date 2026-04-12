#!/bin/bash
# Run a Locust load test against a local nginx instance and write CSV
# + console output into this directory. This is the command the
# workflow (and a local `act` run) execute; keeping it in a script
# rather than inline in the YAML makes it easy to iterate locally.
#
# Locust fundamentally measures real HTTP request/response latency
# under a simulated user workload; it needs an HTTP target to talk
# to. We stand up nginx in the foreground serving the sibling
# index.html on port 8080, run locust against it in headless mode,
# then `trap` a kill so nginx goes away on any exit (success, error,
# or Ctrl-C).
#
# Locust flags:
#   --headless       — no web UI, no interactive prompts; run and exit.
#   --users 10       — peak concurrent simulated users.
#   --spawn-rate 10  — ramp users up at 10/s (so we hit steady state
#                      inside the first second of the run).
#   --run-time 10s   — total test duration.
#   --csv=output     — write output_stats.csv, output_failures.csv,
#                      and output_stats_history.csv in the cwd.
#   --only-summary   — suppress the periodic per-interval console
#                      table; keep the final aggregate report only.
#   -f locustfile.py — scenario file.
#
# We `tee` stdout+stderr into output.txt so the parser sees the same
# human-readable summary table a local operator would see, in
# addition to the three CSV files.
set -euo pipefail

cd "$(dirname "$0")"

# Clean up any stale nginx state from a previous local run. The
# workflow starts from a fresh checkout so this is only relevant for
# repeated local `./run.sh` invocations.
rm -rf client_body_temp proxy_temp fastcgi_temp uwsgi_temp scgi_temp
rm -f  nginx.pid nginx-error.log
rm -f  output_stats.csv output_failures.csv output_stats_history.csv output.txt

nginx -p "$(pwd)" -c nginx.conf &
NGINX_PID=$!
trap 'kill "${NGINX_PID}" 2>/dev/null || true' EXIT

# Give nginx a beat to bind before locust connects.
for _ in 1 2 3 4 5 6 7 8 9 10; do
    if curl -sSf http://localhost:8080/ >/dev/null 2>&1; then
        break
    fi
    sleep 0.2
done

locust --headless --users 10 --spawn-rate 10 --run-time 10s \
    --csv=output --only-summary -f locustfile.py 2>&1 | tee output.txt
