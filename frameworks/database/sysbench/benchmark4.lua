-- benchmark4 -- monthly change-point showcase.
-- Sleep duration = 2.15 + ((m mod 3) - 1) where m is the current UTC month.
-- Produces a deterministic {1.15, 2.15, 3.15} cycle with period 3 months,
-- so a full year has 11 change points for downstream change-detection
-- tooling to verify against. See ../../../docs/sample-benchmark.md.
--
-- os.date("!%m") uses the '!' flag to force UTC and '%m' for a 2-digit
-- month; tonumber() turns it into an integer for the formula.
-- Sleep mechanism: os.execute("sleep ...") -- same rationale as
-- benchmark1.lua.

function event()
    local m = tonumber(os.date("!%m"))
    local s = 2.15 + (m % 3) - 1
    os.execute("sleep " .. s)
end
