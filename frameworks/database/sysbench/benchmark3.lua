-- benchmark3 -- small write to /dev/null (1.4 MB).
-- See ../../../docs/sample-benchmark.md for the canonical spec.
--
-- 1.4 MB is decimal (1,400,000 bytes), matching the convention used by
-- every other framework in the corpus. The payload is a constant string
-- of 'x' rather than pseudo-random data -- sysbench's Lua environment
-- doesn't ship a urandom reader and the point of this test is to
-- exercise I/O-shaped metrics, not entropy.

function event()
    local f = io.open("/dev/null", "wb")
    local data = string.rep("x", 1400000)
    f:write(data)
    f:close()
end
