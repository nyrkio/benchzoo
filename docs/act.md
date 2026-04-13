# Running workflows locally with `act`

We use [`nektos/act`][act] to run the **exact same workflow YAML files**
locally, inside Docker containers that approximate GitHub's hosted
runners. This is how parser development actually happens in practice:

1. Edit the workflow (or the sample benchmark inside it).
2. Run the workflow locally via `act`, capturing the output artifact to
   a local directory.
3. Copy the artifact into
   `frameworks/<category>/<framework>/fixtures/` (or wherever the
   fixture should live) as the reference input for parser development.
4. Write or iterate on the Python parser against that local fixture.
5. When the parser is green, commit and push. Real GitHub runners
   execute the same workflow as final verification.

The alternative — push every iteration, wait for CI, download the
artifact, repeat — is substantially slower and noisier.

The YAML file is the single source of truth for both act (local) and
GitHub (remote). We do not maintain parallel "local" and "CI" variants.

[act]: https://github.com/nektos/act

## Install

On Kubuntu / Debian-family Linux:

```bash
curl -sSL https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
```

On macOS: `brew install act`.

## Image selection

`act`'s default Docker image is intentionally minimal (no `sudo`, no
Python, no Node, etc.) — most benchzoo workflows will fail on it.
Pick a bigger image either per-invocation:

```bash
act -P ubuntu-latest=catthehacker/ubuntu:full-latest ...
```

…or pin it in `~/.actrc` so every invocation picks it up:

```
-P ubuntu-latest=catthehacker/ubuntu:full-latest
```

The `full` image is ~40 GB but is the closest approximation to GitHub's
hosted `ubuntu-latest`. `catthehacker/ubuntu:act-latest` is smaller and
often enough for simpler workflows that only need common toolchains.

## Running a single workflow

```bash
act push -W .github/workflows/hyperfine.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Explanation:

- `act push` — simulate a `push` event (matching our default trigger).
- `-W .github/workflows/hyperfine.yml` — run only this one workflow,
  not every workflow in the repo.
- `--artifact-server-path /tmp/benchzoo-artifacts` — where
  `actions/upload-artifact` outputs go. Without this flag, artifacts
  live inside the ephemeral container and are tedious to retrieve.

After the run, the captured output lands at:

```
/tmp/benchzoo-artifacts/<run-id>/<artifact-name>/<file>
```

## Simulating a schedule trigger

For workflows that accumulate the change-detection showcase series (see
test 4 in [`sample-benchmark.md`](sample-benchmark.md#test-4--change-detection-showcase-monthly-change-point)),
simulate the cron trigger:

```bash
act schedule -W .github/workflows/<framework>.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

## What act can't do

- **macOS and Windows runners.** act only supports Linux containers.
  Workflows targeting `macos-latest` or `windows-latest` (for example,
  XCTest) must be tested on GitHub proper.
- **Exact image parity.** `catthehacker`'s images approximate
  `ubuntu-latest` but are not byte-identical. If a workflow passes
  under `act` and fails on GitHub (or vice versa), trust GitHub's
  runner and file a local-parity gap; don't fork the workflow.
- **Some GitHub-only integrations.** Anything requiring genuine GitHub
  API context (real installation tokens, real event payloads beyond
  `push`/`schedule`/`pull_request`) may behave differently. act
  provides a placeholder `GITHUB_TOKEN` that works for most cases but
  not all.

## Secrets

Most benchzoo workflows are read-only and need no secrets. If one
does, pass them via `--secret` or `--secret-file`:

```bash
act push -W .github/workflows/foo.yml --secret-file .secrets
```

Keep `.secrets` out of the repo (it should be in `.gitignore`).
