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

# asv publishes per-commit JSON under .asv/results/<machine>/<hash>-<env>.json.
# The machine name defaults to the hostname; on GitHub's runners that is
# something like "fv-az123-456". Glob to find the single commit's result
# file (there is exactly one since we only ran against HEAD).
asv publish

result_file=$(find .asv/results -mindepth 2 -type f -name '*.json' \
    ! -name 'machine.json' ! -name 'benchmarks.json' | head -n 1)

if [[ -z "${result_file}" ]]; then
    echo "ERROR: no asv result JSON found under .asv/results/" >&2
    find .asv/results -type f >&2 || true
    exit 1
fi

cp "${result_file}" output.json
echo "Copied ${result_file} -> output.json"
