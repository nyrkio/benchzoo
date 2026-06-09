"""Minimal ``linetimer`` example for benchzoo — four timed blocks.

``linetimer``'s ``CodeTimer`` prints ``Code block 'NAME' took: <n> <unit>``
to stdout on exit (default unit: milliseconds). We time four named blocks
(``benchmark1``..``benchmark4``) — benchzoo's standard four-benchmark
change-detection showcase. ``benchmark4`` uses ``unit="s"`` the way
``pola-rs/polars-benchmark`` prints its TPC-H query timings, exercising the
parser's unit normalisation. ``run.sh`` tees stdout to ``output.txt``.
"""
import time

from linetimer import CodeTimer

with CodeTimer("benchmark1"):
    time.sleep(0.05)

with CodeTimer("benchmark2"):
    time.sleep(0.10)

with CodeTimer("benchmark3"):
    time.sleep(0.15)

with CodeTimer("benchmark4", unit="s"):
    time.sleep(0.20)
