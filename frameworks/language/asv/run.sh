#!/usr/bin/env bash
# Run the asv sample benchmark and surface the raw results JSON as
# ``output.json`` at the framework dir root.
#
# asv's usual workflow (``asv run`` provisioning its own virtualenv per
# Python version in the matrix) is overkill for this corpus: we already
# pin Python to 3.12 at the CI layer and install asv into that interpreter
# via requirements.txt, so we pass ``--python=same`` to run the benchmarks
# in the current environment instead of letting asv spin up a fresh one.
# ``--quick`` caps samples per benchmark, which matters for the multi-second
# sleep tests (otherwise a single CI run could take minutes).
#
# asv requires the machine to be registered before ``asv run`` will work;
# ``asv machine --yes`` accepts defaults non-interactively.

set -euo pipefail

asv machine --yes

asv run --python=same --quick --show-stderr

# The raw per-commit results JSON under .asv/results/<machine>/<hash>-<env>.json
# is written directly by `asv run` — we do NOT call `asv publish` because
# that step wants to resolve the repo URL for history rendering and chokes
# on `repo: "."` in a shallow CI checkout ("Can not determine what kind of
# DVCS to use for URL '.'"). The raw results file is what the parser
# actually needs; asv publish is purely a human-readable aggregator.
result_file=$(find .asv/results -mindepth 2 -type f -name '*.json' \
    ! -name 'machine.json' ! -name 'benchmarks.json' | head -n 1)

if [[ -z "${result_file}" ]]; then
    echo "ERROR: no asv result JSON found under .asv/results/" >&2
    find .asv/results -type f >&2 || true
    exit 1
fi

cp "${result_file}" output.json
echo "Copied ${result_file} -> output.json"
