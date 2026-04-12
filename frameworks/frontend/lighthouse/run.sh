#!/bin/bash
# Run Lighthouse against a local static page and write the JSON report
# to ./output.json. This is the command the workflow (and a local `act`
# run) execute; keeping it in a script rather than inline in the YAML
# makes it easy to iterate locally.
#
# Lighthouse audits a real page loaded in headless Chrome, so we need a
# real HTTP origin. Python's built-in http.server is enough for this —
# we start it in the background on port 8080, run Lighthouse, and
# `trap` the kill so the server goes away on any exit (success, error,
# or Ctrl-C).
#
# --chrome-flags:
#   --headless=new   — modern headless mode.
#   --no-sandbox     — required in GitHub Actions containers and under
#                      act, because Chrome's sandbox needs kernel
#                      capabilities the container doesn't grant.
#   --disable-gpu    — headless Chrome has no GPU to talk to.
#
# --only-categories=performance limits the audit to the web-vitals
# category, skipping accessibility / SEO / best-practices / PWA. We
# only care about the performance metrics for the parser fixture.
set -euo pipefail

cd "$(dirname "$0")"

python3 -m http.server 8080 --directory ./site >/tmp/benchzoo-lighthouse-http.log 2>&1 &
HTTP_PID=$!
trap 'kill "${HTTP_PID}" 2>/dev/null || true' EXIT

# Give the server a beat to bind before Lighthouse connects.
for _ in 1 2 3 4 5 6 7 8 9 10; do
    if curl -sSf http://localhost:8080/ >/dev/null 2>&1; then
        break
    fi
    sleep 0.2
done

lighthouse http://localhost:8080/ \
    --output=json \
    --output-path=./output.json \
    --chrome-flags="--headless=new --no-sandbox --disable-gpu" \
    --only-categories=performance
