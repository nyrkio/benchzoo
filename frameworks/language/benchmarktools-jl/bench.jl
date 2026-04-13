# Canonical benchzoo sample benchmark under BenchmarkTools.jl.
#
# BenchmarkTools.jl is Julia's de-facto micro-benchmark library. Its
# native machine-readable output is JSON, produced by
# `BenchmarkTools.save(path, result)`. That JSON is what the workflow
# uploads as `output.json` and what the eventual parser consumes.
#
# Each of the four canonical tests is registered under a stable string
# key inside a top-level `BenchmarkGroup()`. Those keys become the
# `test_name` values the parser keys off.
#
# Notes on wall-time budgeting:
#
# BenchmarkTools normally auto-tunes the number of samples and
# evaluations per sample to get a tight estimate. For our sleep-heavy
# benches that would mean dozens of seconds per bench for no useful
# signal — the sleep duration is deterministic; statistical tightness
# is not what we are measuring. We therefore pin `samples=3` and
# `evals=1` for benchmark1 and benchmark4. Tests 2 and 3 are fast
# enough to keep BenchmarkTools's defaults (which still bound total
# wall time via `seconds=5` by default).

using BenchmarkTools
using Dates
using Random

# Top-level group. BenchmarkTools.save serializes this as
# [1, [group-name, content]] (see README.md "JSON format").
suite = BenchmarkGroup()

# ---------------------------------------------------------------------
# Test 1 — sleep-dominated (~2.15 s). Julia's `sleep` accepts a Float64
# number of seconds, so `sleep(2.15)` is exact.
#
# samples=3 keeps total wall time bounded at roughly 3 * 2.15 s ≈ 6.5 s
# per bench rather than BenchmarkTools's default, which would run many
# more samples.
# ---------------------------------------------------------------------
suite["benchmark1"] = @benchmarkable sleep(2.15) samples=3 evals=1 seconds=30

# ---------------------------------------------------------------------
# Test 2 — tight CPU loop (sub-millisecond).
#
# An empty `for i in 1:1000 end` is a prime target for Julia's
# optimizer. `sum(1:1000)` produces the same loop shape but carries a
# data dependency on `i` that the compiler cannot fold away without
# also losing the result — and we further guard against constant
# folding by passing the loop bound through a `Ref`, so the range is
# not a compile-time literal. Wrapping in BenchmarkTools's `$` (or
# `Ref[]` interpolation, as below) is the idiomatic "don't precompute
# this" mechanism for BenchmarkTools, analogous to
# `std::hint::black_box` in Rust or `Blackhole.consume` in JMH.
# ---------------------------------------------------------------------
const TEST2_BOUND = Ref(1000)
suite["benchmark2"] = @benchmarkable sum(1:($TEST2_BOUND)[])

# ---------------------------------------------------------------------
# Test 3 — write 1.4 MB to /dev/null.
#
# `devnull` is Julia's portable "bit bucket" IO object; on Unix it is
# /dev/null, on Windows it is NUL. `rand(UInt8, 1_400_000)` generates
# 1.4 MB of pseudo-random bytes. We seed Random so the byte buffer is
# reproducible across runs — though since `devnull` discards its
# input, the byte values are immaterial anyway; only the count
# matters.
# ---------------------------------------------------------------------
Random.seed!(0)
suite["benchmark3"] = @benchmarkable write(devnull, rand(UInt8, 1_400_000))

# ---------------------------------------------------------------------
# Test 4 — monthly change-point showcase.
#
# Reads UTC month, computes 2.15 + ((m mod 3) - 1), sleeps. See
# docs/sample-benchmark.md § "Test 4" for the formula and its
# purpose. Month is captured once at script start so all samples for
# this bench see the same value (we don't want to straddle a month
# boundary mid-run).
# ---------------------------------------------------------------------
const MONTH_UTC = Dates.month(Dates.now(Dates.UTC))
const TEST4_SLEEP = 2.15 + ((MONTH_UTC % 3) - 1)
@info "benchmark4 month/sleep" month=MONTH_UTC sleep_s=TEST4_SLEEP
suite["benchmark4"] = @benchmarkable sleep($TEST4_SLEEP) samples=3 evals=1 seconds=30

# ---------------------------------------------------------------------
# Run and save.
#
# `run(suite)` executes every registered benchmark and returns a
# BenchmarkGroup of Trial objects. BenchmarkTools.save then serializes
# the whole group to JSON in its tagged format (see README.md).
# ---------------------------------------------------------------------
results = run(suite; verbose=true)

BenchmarkTools.save("output.json", results)

println("--- results summary ---")
for name in ("benchmark1", "benchmark2", "benchmark3", "benchmark4")
    t = results[name]
    println(name, ": ", t)
end
println("--- wrote output.json ---")
