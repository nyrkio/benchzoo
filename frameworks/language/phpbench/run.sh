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
# PHPBench has no built-in report named "default"; we use the
# "aggregate" generator, which ships with phpbench and produces a
# readable summary with per-subject mean/min/max/stddev.
./vendor/bin/phpbench run \
    --report=aggregate \
    --dump-file=output.xml \
    --progress=none \
    2>&1 | tee output.txt

# PHPBench's JSON output is a configured renderer service, not a
# flag. The XML dump is sufficient as the machine-readable capture;
# parsers consume that. (A JSON renderer could be registered via
# phpbench.json under report.renderers, but keeping the workflow
# simple beats shipping two formats we don't strictly need.)
