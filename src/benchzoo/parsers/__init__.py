"""Parsers that convert framework-native output into Nyrkiö JSON.

Each parser module in this package exposes a single pure function::

    def parse(content: bytes | str) -> list[dict]: ...

Returning a list of flat dicts in the Nyrkiö JSON shape — one dict per
test run found in ``content``. See ``docs/design.md`` for the full
contract.

The data model is plain ``dict`` / ``list`` throughout; there are no
dataclasses, TypedDicts, or Pydantic schemas. The Python representation
is isomorphic to the JSON wire format, so serialization at the edge of
the library is one ``json.dumps()`` call.

A minimal result from a parser looks like::

    [
        {
            "timestamp": 0,
            "metrics": [
                {"name": "mean", "unit": "s", "value": 2.15, "direction": "lower_is_better"},
            ],
            "attributes": {"test_name": "benchmark1"},
            "passed": True,
        },
        ...
    ]

Parsers **must**:

- set ``attributes["test_name"]`` to a stable identifier,
- set ``timestamp`` to ``0`` (the ingest layer fills in the real
  git-commit timestamp later — parsers never read the framework's
  wall-clock time for this field),
- leave the git-related attribute keys (``git_repo``, ``branch``,
  ``git_commit``) out of ``attributes`` entirely,
- populate ``metrics`` from the source output,
- record failed tests with ``passed: False`` rather than dropping them.
"""
