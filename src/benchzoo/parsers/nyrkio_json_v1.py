"""Parser for the historical Nyrkiö JSON format (v1, pre-benchzoo).

This is the shape nyrkio.com ingested for years and that some projects
(notably tigerbeetle's ``devhubdb/devhub/data.json``) still publish. It
predates the benchzoo canonical format but overlaps heavily — the
meaningful difference is that every v1 record carries its own git
provenance inline, whereas modern framework parsers don't (the ingest
layer stitches commit metadata in afterwards from the CI event).

Wire format — either a top-level JSON array (nyrkio.com exports) or
NDJSON with one object per line (tigerbeetle devhubdb). Both parse::

    {
      "timestamp": 1706033544,
      "metrics": [{"name": "...", "value": ..., "unit": "..."}],
      "attributes": {
        "git_repo":   "https://github.com/owner/name",
        "branch":     "main",
        "git_commit": "abc123...",
        # ...any other test-level metadata
      }
    }

Because v1 genuinely knows the commit, we fill a ``commit`` sub-document
on each emitted run — same sub-document shape the rest of the stack
uses for webhook-ingested data (``{commit_time, sha, short_sha, ref,
repo_url}``). That keeps downstream code (facet computation, aurora's
time axis, the commit-link generator in the UI) uniform across ingest
sources. The contract's usual ``timestamp: 0`` still holds because
``timestamp`` is for *test execution* wall-clock, not commit time.

``commit.repo_url`` is kept as the full URL. The ingest layer parses
it to determine platform/owner/name for routing — that belongs in
nyrkiov3, not here.
"""
from __future__ import annotations

import json


def _parse_json_any(blob: str) -> list[dict]:
    blob = blob.strip()
    if not blob:
        return []
    if blob[0] == "[":
        data = json.loads(blob)
        if not isinstance(data, list):
            raise ValueError("expected top-level JSON array")
        return data
    out = []
    for line in blob.splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    rows = _parse_json_any(content)
    out: list[dict] = []
    for row in rows:
        attrs = dict(row.get("attributes") or {})
        git_repo = attrs.pop("git_repo", None)
        ref = attrs.pop("branch", None)
        sha = attrs.pop("git_commit", None)
        test_name = attrs.pop("test_name", None)

        commit: dict = {}
        if isinstance(row.get("timestamp"), (int, float)):
            commit["commit_time"] = int(row["timestamp"])
        if sha:
            commit["sha"] = sha
            commit["short_sha"] = sha[:7]
        if ref:
            commit["ref"] = ref
        if git_repo:
            commit["repo_url"] = git_repo

        run: dict = {
            "test": {"test_name": test_name} if test_name else {},
            "run": {"passed": row.get("passed", True)},
            "env": {"framework": {"name": "nyrkio-v1"}},
            "metrics": row.get("metrics") or [],
        }
        if attrs:
            run["extra_info"] = attrs
        if commit:
            run["commit"] = commit
        out.append(run)
    return out
