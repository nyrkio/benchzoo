-- benchmark3 — emit 1.4 MB of data (canonical spec: "write 1.4 MB to /dev/null").
-- repeat('x', 1400000) builds a deterministic 1,400,000-byte string on the
-- server; returning it to pgbench sends the full payload across the
-- connection, which is arguably a more representative "small I/O" for a
-- client/server database than writing to /dev/null would be. The spec's
-- "pseudo-random" is approximated with a constant byte because the purpose
-- is timing a small fixed-size payload, not a randomness test.
-- See ../../../docs/sample-benchmark.md for the canonical spec.
SELECT octet_length(repeat('x', 1400000));
