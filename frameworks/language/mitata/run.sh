#!/bin/bash
# Run the mitata sample-benchmark and capture its JSON output.
#
# mitata is a library, not a runner — there is no standard output
# format. `sample-benchmark.js` defines the JSON shape it emits on
# stdout (see README.md "Parser notes"). We merge stderr into the same
# file so npm noise and any mitata diagnostic output are preserved
# alongside the JSON; the parser reads only the JSON object.
set -euo pipefail

cd "$(dirname "$0")"

npm install && node sample-benchmark.js > output.json 2>&1
