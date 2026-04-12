-- benchmark2 — tight CPU loop (empty body, 1000 iterations).
-- pgbench's own "\" backslash commands are client-side and do not include a
-- loop construct; PL/pgSQL is the idiomatic way to get an empty loop executed
-- inside the server. A DO $$ ... $$; anonymous block is a single SQL
-- statement from pgbench's perspective, so it slots into a custom script
-- without trouble.
-- See ../../../docs/sample-benchmark.md for the canonical spec.
DO $$
BEGIN
    FOR i IN 0..999 LOOP
        NULL;
    END LOOP;
END
$$;
