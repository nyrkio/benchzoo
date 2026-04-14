"""Parser for JMH's ``-rf csv`` output.

JMH's CSV format is one row per benchmark with columns::

    Benchmark,Mode,Threads,Samples,Score,Score Error (99.9%),Unit

It carries the essential per-benchmark summary (score, error, unit,
mode, thread count, sample count) but lacks the raw iteration data,
percentiles, and secondary metrics present in the JSON format.

See ``frameworks/language/jmh/README.md`` for the parser notes this
implementation follows.
"""

from __future__ import annotations

import csv
import io


_LOWER_IS_BETTER_MODES = {"avgt", "sample", "ss"}
_HIGHER_IS_BETTER_MODES = {"thrpt"}


def _direction_for_mode(mode: str) -> str | None:
    if mode in _LOWER_IS_BETTER_MODES:
        return "lower_is_better"
    if mode in _HIGHER_IS_BETTER_MODES:
        return "higher_is_better"
    return None


def _short_name(fqn: str) -> str:
    return fqn.rsplit(".", 1)[-1]


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    reader = csv.DictReader(io.StringIO(content))

    # JMH names the error column with a confidence-level suffix, e.g.
    # "Score Error (99.9%)". Detect it dynamically instead of
    # hardcoding the confidence level.
    error_col = next(
        (c for c in (reader.fieldnames or []) if c.startswith("Score Error")),
        None,
    )

    out: list[dict] = []
    for row in reader:
        mode = row.get("Mode", "")
        direction = _direction_for_mode(mode)
        unit = row.get("Unit", "")

        score_metric: dict = {
            "name": "score",
            "unit": unit,
            "value": float(row["Score"]),
        }
        if direction is not None:
            score_metric["direction"] = direction

        error_value = None
        if error_col is not None and row.get(error_col, "") != "":
            try:
                error_value = float(row[error_col])
            except ValueError:
                error_value = None

        error_metric: dict = {
            "name": "score_error",
            "unit": unit,
            "value": error_value,
        }
        if direction is not None:
            error_metric["direction"] = direction

        params: dict = {"mode": mode}
        if "Threads" in row and row["Threads"] != "":
            params["threads"] = int(row["Threads"])
        if "Samples" in row and row["Samples"] != "":
            params["samples"] = int(row["Samples"])

        fqn = row["Benchmark"]
        test: dict = {"test_name": _short_name(fqn), "params": params}
        if "." in fqn:
            test["group"] = fqn.rsplit(".", 1)[0]

        out.append({
            "test": test,
            "run": {"passed": True},
            "env": {"framework": {"name": "jmh"}},
            "metrics": [score_metric, error_metric],
        })

    return out
