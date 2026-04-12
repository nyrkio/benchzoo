#!/usr/bin/env bash
# Run the sample Jest tests and emit JUnit XML to ./output.xml.
#
# jest-junit's output path is configured in package.json under the
# "jest-junit" key (outputDirectory + outputName), so the reporter
# writes ./output.xml without any extra flags.
set -euo pipefail

npm install
npx jest --reporters=default --reporters=jest-junit
