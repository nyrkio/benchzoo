#!/usr/bin/env bash
# Install PHPBench and run the canonical sample benchmark, capturing
# both the native XML dump (rich, per-iteration detail) and the console
# text output. A second run captures PHPBench's JSON aggregate report
# via the ``json`` output. All three outputs land next to this script
# so the CI workflow can upload them as a single artifact.
set -euo pipefail

composer install --no-interaction --no-progress

# Native XML dump: PHPBench's internal suite format, rich per-iteration.
# Also keep the console default report as plain text alongside.
./vendor/bin/phpbench run \
    --report=default \
    --dump-file=output.xml \
    --progress=none \
    2>&1 | tee output.txt

# JSON aggregate report: the ``aggregate`` report rendered via the
# ``json`` output. One summary row per subject/variant.
./vendor/bin/phpbench run \
    --report=aggregate \
    --output='json:path=output.json' \
    --progress=none \
    >/dev/null
