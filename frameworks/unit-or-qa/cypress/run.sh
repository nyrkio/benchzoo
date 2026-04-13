#!/usr/bin/env bash
# Run the sample Cypress tests and emit JUnit XML to ./output.xml.
#
# mocha-junit-reporter's output path is configured in cypress.config.js
# (reporterOptions.mochaFile), so the reporter writes ./output.xml
# without any extra flags. Cypress bundles its own Electron browser, so
# no additional browser install is needed on the runner.
set -euo pipefail

npm install
npx cypress run --headless --browser=electron
