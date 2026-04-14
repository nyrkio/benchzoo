"""Parser for Playwright's ``--reporter=json`` output.

Playwright's JSON reporter emits a nested tree::

    {
      "stats": {"startTime": ..., "duration": ..., "expected": 4,
                "skipped": 0, "unexpected": 0, "flaky": 0},
      "suites": [
        {
          "file": "tests/sample.spec.ts",
          "specs": [
            {
              "title": "benchmark1",
              "tests": [
                {
                  "projectId": "chromium",
                  "results": [
                    {"status": "passed", "duration": 2159,
                     "workerIndex": 0, "retry": 0, ...}
                  ],
                  "status": "expected"
                }
              ]
            }
          ]
        }
      ]
    }

One Nyrkiö dict per (spec, project) pair. ``test_name`` is the
spec's ``title``. If a test ran against multiple browser projects
(Playwright's ``projects`` array), each project becomes its own
dict with the project name captured in ``extra_info["project"]``.

Durations are in **milliseconds**.

See ``frameworks/unit-or-qa/playwright/README.md``.
"""

from __future__ import annotations

import json


def _walk_suites(suites: list[dict]) -> list[tuple[dict, dict]]:
    """Recursively walk (sub)suites, yielding (spec, test) pairs."""
    out: list[tuple[dict, dict]] = []
    for suite in suites:
        for spec in suite.get("specs", []):
            for test in spec.get("tests", []):
                out.append((spec, test))
        # Playwright allows nested suites (from describe blocks);
        # recurse.
        out.extend(_walk_suites(suite.get("suites", [])))
    return out


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    doc = json.loads(content)

    out: list[dict] = []
    for spec, test in _walk_suites(doc.get("suites", [])):
        title = spec.get("title", "").strip()
        if not title:
            continue

        project = test.get("projectName") or test.get("projectId") or ""
        results = test.get("results", [])
        if not results:
            continue
        # Use the last (successful-retry) result's numbers.
        final = results[-1]
        duration_ms = float(final.get("duration") or 0)
        status = final.get("status", "")
        passed = status == "passed"

        metrics = [{
            "name": "duration",
            "unit": "ms",
            "value": duration_ms,
            "direction": "lower_is_better",
        }]

        params: dict = {}
        if project:
            params["project"] = project

        extra_info: dict = {}
        if test.get("expectedStatus"):
            extra_info["expected_status"] = test["expectedStatus"]
        if len(results) > 1:
            extra_info["retries"] = len(results) - 1

        test_doc: dict = {"test_name": title}
        if params:
            test_doc["params"] = params

        result_dict = {
            "test": test_doc,
            "run": {"passed": passed},
            "env": {"framework": {"name": "playwright"}},
            "metrics": metrics,
        }
        if extra_info:
            result_dict["extra_info"] = extra_info
        out.append(result_dict)

    return out
