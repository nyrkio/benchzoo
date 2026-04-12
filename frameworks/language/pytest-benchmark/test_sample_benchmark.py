"""Canonical sample benchmark implemented for pytest-benchmark.

Each test function corresponds to one of the four canonical tests in
``docs/sample-benchmark.md``. The function names (``test_benchmark1`` ..
``test_benchmark4``) are chosen so a parser can map directly from
``benchmarks[i].name`` to ``attributes["test_name"] = "benchmark1"`` etc.
by stripping the ``test_`` prefix.

pytest-benchmark auto-calibrates the number of rounds per test, so we
do not hand-tune ``--benchmark-min-rounds`` here. The default behavior:

- Long-running tests (e.g. the ~2.15 s sleeps) get a small number of
  rounds (typically 5).
- Sub-millisecond tests (the empty loop) get many rounds with an inner
  iteration count chosen so each round takes a measurable amount of
  time.

Groups
------
Tests are assigned to groups via ``@pytest.mark.benchmark(group=...)``.
This exercises pytest-benchmark's ``group`` field in the JSON output,
which the parser should record as ``extra_info["group"]``. Downstream
UIs can use group for drill-down navigation (e.g. select a group first,
then view the tests in it) or for organizing tests onto separate graphs.

- ``sleep`` — tests dominated by sleep (benchmark1, benchmark4). These
  are wall-clock tests where the sleep duration is the primary signal.
- ``compute`` — tests dominated by CPU work or I/O (benchmark2,
  benchmark3). These are fast, CPU-bound or IO-bound tests.
"""

import datetime
import os

import pytest

_PAYLOAD_SIZE = 1_400_000


@pytest.mark.benchmark(group="sleep")
def test_benchmark1(benchmark):
    """Sleep-dominated: wall time ~2.15 s."""
    import time

    def sleep_2_15():
        time.sleep(2.15)

    benchmark(sleep_2_15)


@pytest.mark.benchmark(group="compute")
def test_benchmark2(benchmark):
    """Tight CPU loop: empty ``for _ in range(1000): pass``.

    Python does not eliminate empty loops, so no ``black_box`` trick is
    needed. pytest-benchmark will auto-calibrate the inner iteration
    count so each timed round lasts long enough to measure reliably.
    """

    def tight_loop():
        for _ in range(1000):
            pass

    benchmark(tight_loop)


@pytest.mark.benchmark(group="compute")
def test_benchmark3(benchmark):
    """Write 1,400,000 bytes of urandom to /dev/null."""

    def write_urandom():
        data = os.urandom(_PAYLOAD_SIZE)
        with open("/dev/null", "wb") as devnull:
            devnull.write(data)

    benchmark(write_urandom)


@pytest.mark.benchmark(group="sleep")
def test_benchmark4(benchmark):
    """Monthly change-point showcase.

    Sleep duration in seconds is ``2.15 + ((month % 3) - 1)`` where
    ``month`` is the current UTC month (1..12). This produces the
    step-function series described in
    ``docs/sample-benchmark.md`` test 4.
    """
    import time

    month = datetime.datetime.now(datetime.timezone.utc).month
    sleep_s = 2.15 + ((month % 3) - 1)

    def sleep_monthly():
        time.sleep(sleep_s)

    benchmark(sleep_monthly)
