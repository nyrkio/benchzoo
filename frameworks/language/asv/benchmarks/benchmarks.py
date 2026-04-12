"""Canonical sample benchmark implemented for asv (airspeed velocity).

asv discovers ``time_*`` methods on benchmark classes and times them
per-call, running each multiple times to gather statistics (min, mean,
median, etc.). The method names ``time_benchmark1`` .. ``time_benchmark4``
are chosen so a parser can map directly to
``attributes["test_name"] = "benchmark1"`` etc. by stripping the
``time_`` prefix.

See ``docs/sample-benchmark.md`` for the canonical four-test suite.
"""

import datetime
import os
import time


_PAYLOAD_SIZE = 1_400_000


class SampleBenchmark:
    """Four-method benchmark class covering the canonical sample suite."""

    # asv's default timing loop will call each ``time_*`` method many
    # times and record statistics. --quick (used in run.sh) caps the
    # number of samples to keep CI time reasonable for the multi-second
    # sleep tests.

    def time_benchmark1(self):
        """Sleep-dominated: wall time ~2.15 s."""
        time.sleep(2.15)

    def time_benchmark2(self):
        """Tight CPU loop: empty ``for _ in range(1000): pass``.

        Python does not eliminate empty loops, so no ``black_box`` trick
        is needed.
        """
        for _ in range(1000):
            pass

    def time_benchmark3(self):
        """Write 1,400,000 bytes of urandom to /dev/null."""
        data = os.urandom(_PAYLOAD_SIZE)
        with open("/dev/null", "wb") as devnull:
            devnull.write(data)

    def time_benchmark4(self):
        """Monthly change-point showcase.

        Sleep duration in seconds is ``2.15 + ((month % 3) - 1)`` where
        ``month`` is the current UTC month (1..12).
        """
        month = datetime.datetime.now(datetime.timezone.utc).month
        sleep_s = 2.15 + ((month % 3) - 1)
        time.sleep(sleep_s)
