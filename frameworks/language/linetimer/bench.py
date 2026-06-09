"""benchzoo canonical sample benchmark — linetimer edition.

Implements the four canonical benchmarks from ``docs/sample-benchmark.md``
(identical across every framework) wrapped in ``linetimer`` ``CodeTimer``
blocks, so the captured stdout — ``Code block 'benchmarkN' took: <n> ms`` —
feeds the benchzoo ``linetimer`` parser. linetimer's default unit
(milliseconds) is used as-is; the parser normalises to seconds.

``run.sh`` tees this script's stdout to ``output.txt``.
"""
import datetime
import os
import time

from linetimer import CodeTimer

# Test 1 — sleep-dominated (~2.15 s wall time).
with CodeTimer("benchmark1"):
    time.sleep(2.15)

# Test 2 — tight CPU loop, sub-millisecond. Python does not optimise the
# empty loop away, so no black_box equivalent is needed.
with CodeTimer("benchmark2"):
    for _ in range(1000):
        pass

# Test 3 — write exactly 1.4 MB (decimal) of random data to /dev/null.
with CodeTimer("benchmark3"):
    with open("/dev/null", "wb") as devnull:
        devnull.write(os.urandom(1_400_000))

# Test 4 — change-detection showcase: sleep = 2.15 + ((m mod 3) - 1) where
# m is the current UTC month, cycling {1.15, 2.15, 3.15} s with one step
# change at every month boundary.
month = datetime.datetime.now(datetime.timezone.utc).month
with CodeTimer("benchmark4"):
    time.sleep(2.15 + ((month % 3) - 1))
