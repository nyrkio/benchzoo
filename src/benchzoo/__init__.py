"""benchzoo — parsers for benchmark and unit-test framework output.

See ``docs/design.md`` for the architecture and ``docs/parser-targets.md``
for the list of supported formats.

Top-level convenience re-exports:

- :func:`benchzoo.find_parser` — look up a parser module by framework
  name and (optional) format.
- :func:`benchzoo.sniff` — guess the framework from raw output content.
- :data:`benchzoo.PARSERS` — the static framework → parser registry.
"""

from benchzoo.parsers import PARSERS, find_parser
from benchzoo.sniff import sniff

__version__ = "0.0.0"

__all__ = ["PARSERS", "find_parser", "sniff", "__version__"]
