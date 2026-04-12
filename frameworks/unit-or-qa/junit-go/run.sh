#!/bin/bash
# Run the canonical sample benchmark as regular `go test` unit tests,
# wrapped by gotestsum so that per-test timings are emitted as JUnit
# XML into ./output.xml.
#
# gotestsum is a drop-in wrapper around `go test` that consumes the
# `-json` stream and re-emits it in various formats — including
# standard JUnit XML, which is what the `junit_go` parser consumes.
# Using gotestsum (rather than, say, `go-junit-report`) means we can
# also keep a human-readable live-progress log via --format.
#
# Version pin: gotestsum v1.12.0. See workflow-conventions.md — the
# captured fixture must be a function of a known input, so the exact
# gotestsum version lives here rather than floating at @latest.
set -euo pipefail

cd "$(dirname "$0")"

go install gotest.tools/gotestsum@v1.12.0

# $(go env GOPATH)/bin isn't necessarily on PATH under all runners;
# invoke the binary by its absolute path to avoid surprises.
GOTESTSUM="$(go env GOPATH)/bin/gotestsum"

"$GOTESTSUM" --format=standard-verbose --junitfile=output.xml ./...
