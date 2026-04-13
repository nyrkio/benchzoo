#!/usr/bin/env bash
# Run the sample Mocha tests and emit mocha's native JSON reporter output
# to ./output.json.
#
# Mocha's `--reporter json` writes the single JSON document to stdout, so
# we redirect stdout to output.json. stderr is left on the console so
# install/runtime errors are still visible in CI logs.
#
# We intentionally do NOT use `set -e` around the mocha invocation: if a
# test fails, mocha exits non-zero but the JSON document on stdout is
# still the fixture we want to capture (failed runs are recorded, not
# filtered — see docs/design.md "Library boundaries"). The canonical
# sample tests here all pass, so in practice this doesn't come up, but
# the redirect shape is the right one either way.
set -euo pipefail

npm install
npx mocha test/sample.test.js --reporter json --timeout 10000 > output.json
