# linetimer

[`linetimer`](https://pypi.org/project/linetimer/) is a tiny Python timing
library whose `CodeTimer` context manager prints one line per timed block:

```
Code block 'Run polars query 1' took: 1.50120 s
```

Real-world source: [`pola-rs/polars-benchmark`](https://github.com/pola-rs/polars-benchmark)
times each TPC-H query with a `CodeTimer`, so polars' `benchmark-remote.yml`
job log is a wall of these lines. The benchzoo `linetimer` parser scans for
them (tolerating the GitHub Actions per-line timestamp prefix, since the
output usually lives only in a job log, not an artifact) and normalises the
elapsed time to seconds.

`run.sh` runs `bench.py` and tees stdout to `output.txt`.
