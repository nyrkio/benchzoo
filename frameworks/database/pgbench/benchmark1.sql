-- benchmark1 — sleep-dominated (~2.15 s).
-- pgbench custom script: a single SQL statement that sleeps inside the server.
-- pg_sleep() accepts float seconds, so 2.15 is passed through verbatim.
-- See ../../../docs/sample-benchmark.md for the canonical spec.
SELECT pg_sleep(2.15);
