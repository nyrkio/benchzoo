#!/bin/bash
# Run a Gatling load test against a local nginx instance and write the
# simulation.log to ./output.log. This is the command the workflow (and
# a local `act` run) execute; keeping it in a script rather than inline
# in the YAML makes it easy to iterate locally.
#
# Gatling fundamentally measures real HTTP request/response latency; it
# needs an HTTP target to talk to. We stand up nginx in the foreground
# serving the sibling index.html on port 8080, run Gatling against it,
# then `trap` a kill so nginx goes away on any exit.
#
# The Java simulation in src/main/java/sample/BenchSimulation.java
# configures:
#   - HttpProtocolBuilder pointing at http://localhost:8080
#   - one scenario named "homepage" doing http("get /").get("/")
#   - open-model injection: constantUsersPerSec(10) during 5 seconds,
#     i.e. ~50 virtual users each firing one GET against /.
#
# Gatling writes its output under target/gatling/<simulation-timestamp>/,
# containing simulation.log (tab-separated event log, the machine-
# readable primary output) plus an HTML report (index.html + js/css).
# After the run we copy simulation.log to ./output.log so the workflow
# artifact path matches the "one known filename" convention used by the
# rest of the corpus.
set -euo pipefail

cd "$(dirname "$0")"

# Clean up any stale nginx state from a previous local run. The
# workflow starts from a fresh checkout so this is only relevant for
# repeated local `./run.sh` invocations.
rm -rf client_body_temp proxy_temp fastcgi_temp uwsgi_temp scgi_temp
rm -f  nginx.pid nginx-error.log
rm -rf target/gatling

nginx -p "$(pwd)" -c nginx.conf &
NGINX_PID=$!
trap 'kill "${NGINX_PID}" 2>/dev/null || true' EXIT

# Give nginx a beat to bind before Gatling connects.
for _ in 1 2 3 4 5 6 7 8 9 10; do
    if curl -sSf http://localhost:8080/ >/dev/null 2>&1; then
        break
    fi
    sleep 0.2
done

mvn -q gatling:test -Dgatling.simulationClass=sample.BenchSimulation

# Gatling writes to target/gatling/<simulation-timestamp>/simulation.log.
# There's exactly one simulation run per invocation so we grab the first
# (and only) simulation.log we find.
SIM_LOG="$(find target/gatling -type f -name simulation.log -print -quit)"
cp "${SIM_LOG}" output.log
