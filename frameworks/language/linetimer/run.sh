#!/usr/bin/env bash
# Run the linetimer sample and capture its stdout — the "Code block 'NAME'
# took: <n> <unit>" lines — to output.txt for the benchzoo parser.
set -euo pipefail
python bench.py 2>&1 | tee output.txt
