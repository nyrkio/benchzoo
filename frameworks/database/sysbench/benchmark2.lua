-- benchmark2 -- tight CPU loop (sub-millisecond).
-- See ../../../docs/sample-benchmark.md for the canonical spec.
--
-- Lua is interpreted, so the empty loop is not optimized away -- no
-- black_box equivalent is needed. sysbench calls event() once per
-- --events value; with --events=1, the reported per-event latency is
-- the cost of a single execution of this 1000-iteration loop.

function event()
    for i = 1, 1000 do end
end
