"""Parser for ``cargo bench`` / Rust libtest ``#[bench]`` output.

libtest's output format is byte-identical to criterion's
``--output-format bencher``: one line per benchmark with
``test <name> ... bench: <ns> ns/iter (+/- <deviation>)``.

Because the format is the same, this module is a thin delegator to
:mod:`benchzoo.parsers.criterion_bencher`. It exists as a separate
parser module primarily for discoverability — users reaching for a
"cargo bench" parser should find one by name.

See ``frameworks/language/cargo-bench/README.md``.
"""

from __future__ import annotations

from benchzoo.parsers import criterion_bencher


def parse(content: bytes | str) -> list[dict]:
    """Delegate to :func:`benchzoo.parsers.criterion_bencher.parse`."""
    return criterion_bencher.parse(content, framework_name="cargo-bench")
