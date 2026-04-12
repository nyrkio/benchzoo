-- benchmark4 — monthly change-point showcase.
-- Sleep duration = 2.15 + ((m mod 3) - 1) where m is the current UTC month.
-- Produces a deterministic {1.15, 2.15, 3.15} cycle with period 3 months,
-- so a full year has 11 change points for downstream change-detection
-- tooling to verify against. Single SQL statement so it works as a pgbench
-- custom script.
-- See ../../../docs/sample-benchmark.md for the canonical spec.
SELECT pg_sleep(2.15 + (EXTRACT(MONTH FROM NOW() AT TIME ZONE 'UTC')::int % 3 - 1));
