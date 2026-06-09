# linetimer

[`linetimer`](https://pypi.org/project/linetimer/) is a tiny Python timing
library whose `CodeTimer` context manager prints one line per timed block
(default unit: milliseconds):

```
Code block 'benchmark1' took: 2150.28821 ms
```

`bench.py` implements the four canonical benchmarks from
[`docs/sample-benchmark.md`](../../../docs/sample-benchmark.md) — identical
across every framework — each wrapped in a `CodeTimer`. `run.sh` runs it and
tees stdout to `output.txt`, which the workflow uploads as an artifact.

Real-world source: [`pola-rs/polars-benchmark`](https://github.com/pola-rs/polars-benchmark)
times each TPC-H query with a `CodeTimer` (overriding the unit to seconds),
so polars' `benchmark-remote.yml` job log is a wall of these lines with no
artifact. The benchzoo `linetimer` parser scans for them — tolerating the
GitHub Actions per-line timestamp prefix, since that output lives only in
the job log — and normalises every elapsed time to seconds.
