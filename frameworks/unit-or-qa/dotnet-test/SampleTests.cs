// xUnit implementation of the canonical benchzoo sample benchmark,
// consumed by `dotnet test --logger trx`. See
// ../../../docs/sample-benchmark.md for the spec.
//
// Notes on the shape of this file:
//
// * `dotnet test` records per-test wall-clock duration in its TRX
//   (Visual Studio Test Results) XML output. Each `[Fact]` method here
//   becomes a `<UnitTestResult>` element in output.trx with a
//   `duration="hh:mm:ss.fffffff"` attribute — that attribute is the
//   per-test wall time the parser will read.
//
// * Unlike BenchmarkDotNet, there is no pilot / warmup / iteration
//   loop: `dotnet test` runs each test method exactly once, records its
//   duration, and moves on. That means test 2 (tight CPU loop) is going
//   to be dominated by test-runner overhead — the actual loop is
//   sub-microsecond while the recorded duration will be in the tens of
//   milliseconds. That is *fine*: the point of test 2 across the corpus
//   is to exercise sub-millisecond measurement paths in parsers, and
//   `dotnet test`'s duration field just happens not to be a
//   sub-millisecond measurement path. The ground-truth assertion for
//   test 2 accepts a wide range for exactly this reason.
//
// * Benchmark2 still returns the loop accumulator and uses it in an
//   `Assert.True(...)` call. The JIT could in principle elide the loop
//   if the result were unused; pulling the sum through an assertion is
//   the xUnit-idiomatic way to keep the computation observable.
//
// * Benchmark3 writes to /dev/null. That path is Unix-only; the
//   workflow pins ubuntu-latest. On Windows this test would throw.
//
// * Benchmark4 reads DateTime.UtcNow.Month — UTC is load-bearing (see
//   docs/sample-benchmark.md). The sleep formula
//   `2.15 + ((m mod 3) - 1)` cycles through {1.15, 2.15, 3.15} seconds
//   with a change point at every month boundary, for the downstream
//   change-detection showcase.

using System;
using System.IO;
using System.Threading;
using Xunit;

namespace BenchzooSample;

public class SampleTests
{
    // Test 1 — sleep-dominated (~2.15 s). Verifies the parser reads the
    // TRX `duration` attribute as wall-clock time, not CPU time.
    [Fact]
    public void Benchmark1()
    {
        Thread.Sleep(2150);
    }

    // Test 2 — tight CPU loop. The loop body itself is sub-microsecond;
    // the recorded TRX duration will be dominated by xUnit's per-test
    // fixture / reflection overhead (tens of ms range). Pulling `sum`
    // through Assert.True keeps the loop from being optimised away.
    [Fact]
    public void Benchmark2()
    {
        int sum = 0;
        for (int i = 0; i < 1000; i++)
        {
            sum += i;
        }
        Assert.True(sum >= 0);
    }

    // Test 3 — write 1,400,000 bytes of pseudo-random data to
    // /dev/null. Seeded Random keeps the buffer deterministic across
    // runs. /dev/null is Unix-only; the workflow pins ubuntu-latest.
    [Fact]
    public void Benchmark3()
    {
        var buffer = new byte[1_400_000];
        var rng = new Random(42);
        rng.NextBytes(buffer);
        using var stream = File.OpenWrite("/dev/null");
        stream.Write(buffer, 0, buffer.Length);
    }

    // Test 4 — monthly change-point showcase. sleep_time = 2.15 +
    // ((m mod 3) - 1) where m is DateTime.UtcNow.Month. UTC (not .Now)
    // is load-bearing: the value must be the same on the same calendar
    // day regardless of runner timezone. See docs/sample-benchmark.md.
    [Fact]
    public void Benchmark4()
    {
        int month = DateTime.UtcNow.Month;
        double sleepSeconds = 2.15 + ((month % 3) - 1);
        Thread.Sleep((int)(sleepSeconds * 1000));
    }
}
