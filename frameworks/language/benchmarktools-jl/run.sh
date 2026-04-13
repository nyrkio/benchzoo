#!/bin/bash
# Run the canonical sample benchmark under BenchmarkTools.jl and write
# the native JSON output to ./output.json.
#
# BenchmarkTools.jl's native machine-readable output is JSON, produced
# by `BenchmarkTools.save(path, result)`. The JSON carries tagged type
# information — it is not a "naive" dump of Trial fields but a
# BenchmarkTools-specific serialization scheme. See README.md for the
# shape.
#
# The first invocation below instantiates the project, resolving
# Project.toml into a Manifest.toml and downloading BenchmarkTools at
# the pinned version. On CI this happens inside a fresh Julia depot;
# locally with `act` it runs inside a Docker container so it is
# likewise fresh. Subsequent runs in the same depot are fast.
set -euo pipefail

cd "$(dirname "$0")"

rm -f output.json

julia --project=. -e 'using Pkg; Pkg.instantiate()'
julia --project=. bench.jl

ls -la output.json
echo "--- head of output.json ---"
head -c 500 output.json
echo
