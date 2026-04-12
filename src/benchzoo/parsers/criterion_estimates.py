"""Parser for criterion's ``estimates.json`` files.

Criterion writes a directory tree under ``target/criterion/``, with
one subdirectory per benchmark containing a ``new/estimates.json``
file. Our ``run.sh`` flattens those into
``output/<benchmark_name>.json`` for easy artifact upload.

Each estimates file has the shape::

    {
      "mean":   {"point_estimate": 2150115652.8, "standard_error": ...,
                 "confidence_interval": {"lower_bound": ..., "upper_bound": ...,
                                         "confidence_level": 0.95}},
      "median":          { ... same shape ... },
      "median_abs_dev":  { ... same shape ... },
      "std_dev":         { ... same shape ... },
      "slope":           null  (unless criterion measured linear regression)
    }

**All values are in nanoseconds** (raw ``f64``), regardless of how the
terminal pretty-printer renders them.

Because ``parse(content)`` takes the content of ONE file, this parser
returns a single-element list. A caller that wants all four benchmarks
reads the four files and concatenates the results — the fixture layout
is ``output/benchmark1.json``, ``output/benchmark2.json``, etc., and
the test_name is not in the file content (it's in the filename). We
therefore also expose ``parse_directory(path_or_bytes_for_named)``
below, but the minimal public API is ``parse(content) ->
list[dict]`` — same contract as every other benchzoo parser.

**Limitation**: a single ``estimates.json`` does not know its own
benchmark name. The ``parse()`` entry point sets
``attributes["test_name"] = "<unknown>"``; use ``parse_file(path)`` or
``parse_directory(dir)`` when you have a filename or directory so the
test_name can be recovered.

See ``frameworks/language/criterion/README.md``.
"""

from __future__ import annotations

import json
import pathlib


def _parse_one(obj: dict, test_name: str) -> dict:
    metrics = []
    # Criterion's 'mean' and 'median' are the headline; std_dev is
    # variability. 'median_abs_dev' is MAD, useful for robust stats.
    # 'slope' is only set for throughput benches with linear regression
    # — usually null for our sleep-heavy tests.
    for key in ("mean", "median", "median_abs_dev", "std_dev"):
        section = obj.get(key)
        if section is None:
            continue
        metrics.append({
            "name": key,
            "unit": "ns",
            "value": section["point_estimate"],
            "direction": "lower_is_better",
        })

    return {
        "timestamp": 0,
        "attributes": {"test_name": test_name},
        "metrics": metrics,
        "passed": True,
    }


def parse(content: bytes | str) -> list[dict]:
    """Parse one estimates.json document.

    The test_name is unknown from the file content alone; the returned
    dict has ``attributes["test_name"] = "<unknown>"``. Use
    :func:`parse_file` or :func:`parse_directory` when you know the
    filename.
    """
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    return [_parse_one(json.loads(content), "<unknown>")]


def parse_file(path: str | pathlib.Path) -> list[dict]:
    """Parse one estimates.json file, using the filename stem as test_name."""
    p = pathlib.Path(path)
    return [_parse_one(json.loads(p.read_text()), p.stem)]


def parse_directory(dir_path: str | pathlib.Path) -> list[dict]:
    """Parse every ``<name>.json`` file in a directory.

    Our ``run.sh`` flattens criterion's nested ``target/criterion/``
    tree into a single directory with one ``<benchmark_name>.json``
    file per benchmark.
    """
    d = pathlib.Path(dir_path)
    out: list[dict] = []
    for p in sorted(d.glob("*.json")):
        out.extend(parse_file(p))
    return out
