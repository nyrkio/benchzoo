-- benchmark1 -- sleep-dominated (~2.15 s).
-- See ../../../docs/sample-benchmark.md for the canonical spec.
--
-- sysbench runs event() once per --events value. With --events=1, this
-- fires exactly one sleep and reports the per-event latency in the
-- "Latency" block of its text output.
--
-- Sleep mechanism: os.execute("sleep 2.15"). Lua has no portable
-- sub-second sleep in its standard library, and sysbench's Lua
-- environment does not expose a ready-made sysbench.os.sleep helper
-- we can rely on across distro-packaged versions. GNU coreutils `sleep`
-- accepts fractional seconds, so shelling out is the simplest portable
-- choice. The cost is one fork+exec per event, which adds a few
-- milliseconds on top of the 2.15 s sleep -- acceptable for a
-- parser-corpus benchmark where the dominant signal is the sleep itself.

function event()
    os.execute("sleep 2.15")
end
