// BenchmarkDotNet implementation of the canonical benchzoo sample
// benchmark. See ../../../docs/sample-benchmark.md for the spec.
//
// A few BenchmarkDotNet-specific notes that drive the attribute choices
// below:
//
// * BenchmarkDotNet's default job runs a multi-stage pilot + warmup +
//   many-iteration main phase, which is wildly inappropriate for a
//   benchmark whose headline measurement is a 2.15-second Thread.Sleep.
//   A default run of Benchmark1 would sleep for minutes. We use
//   [SimpleJob(RunStrategy.Monitoring, ...)] — Monitoring is the
//   strategy BenchmarkDotNet documents for long / noisy / real-world
//   measurements where per-invocation overhead is negligible and you
//   just want a small fixed number of actual invocations measured.
//   iterationCount: 3 keeps total wall time modest (roughly
//   3 * (2.15 + small + small + 2.15) seconds plus startup) while still
//   producing enough samples for Statistics.Mean / StandardDeviation to
//   be meaningful.
//
// * [JsonExporterAttribute.Full] makes BenchmarkDotNet emit the full
//   JSON report (the "-report-full.json" variant) which includes both
//   the Statistics dict and the per-iteration Measurements[] array.
//   That's the format run.sh copies to ./output.json for the workflow
//   artifact. [CsvExporter] additionally emits a CSV report with
//   columns like Method, Job, Mean, Error, StdDev, etc., which run.sh
//   copies to ./output.csv.
//
// * Benchmark2 returns the loop accumulator. BenchmarkDotNet's user
//   guide explicitly documents that returning a value from a benchmark
//   method is the idiomatic way to prevent dead-code elimination: the
//   runtime can't prove the returned value is unused, so the JIT keeps
//   the computation. The other three tests don't need this guard
//   (Thread.Sleep, file I/O, and DateTime.UtcNow are all side-effecting
//   and cannot be optimised away).
//
// * Benchmark3 writes to /dev/null. That path exists only on Unix, so
//   this class will throw on Windows. The workflow pins
//   runs-on: ubuntu-latest, which is fine, but running this under
//   Windows or macOS without adjustment will fail at Benchmark3.

using System;
using System.IO;
using System.Threading;
using BenchmarkDotNet.Attributes;
using BenchmarkDotNet.Engines;
using BenchmarkDotNet.Exporters.Csv;
using BenchmarkDotNet.Jobs;

namespace BenchzooSample;

[JsonExporterAttribute.Full]
[CsvExporter]
[SimpleJob(RunStrategy.Monitoring, iterationCount: 3)]
public class SampleBenchmark
{
    // Test 1 — sleep-dominated (~2.15 s). Void return is fine here:
    // Thread.Sleep is a side-effecting syscall, so there is nothing for
    // the JIT to elide.
    [Benchmark]
    public void Benchmark1()
    {
        Thread.Sleep(2150);
    }

    // Test 2 — tight CPU loop (sub-millisecond). Returning the
    // accumulator is the BenchmarkDotNet-documented idiom for
    // suppressing dead-code elimination; without it the JIT would be
    // free to delete the loop body entirely and report zero.
    [Benchmark]
    public int Benchmark2()
    {
        int sum = 0;
        for (int i = 0; i < 1000; i++)
        {
            sum += i;
        }
        return sum;
    }

    // Test 3 — write 1,400,000 bytes of pseudo-random data to
    // /dev/null. The byte buffer is filled from a seeded Random so the
    // output is deterministic across runs. The /dev/null path is
    // Linux-specific (and macOS-compatible); on Windows this throws.
    // The workflow pins ubuntu-latest, matching that assumption.
    [Benchmark]
    public void Benchmark3()
    {
        var buffer = new byte[1_400_000];
        var rng = new Random(seed: 42);
        rng.NextBytes(buffer);
        using var stream = File.OpenWrite("/dev/null");
        stream.Write(buffer, 0, buffer.Length);
    }

    // Test 4 — monthly change-point showcase. sleep_time = 2.15 +
    // ((m mod 3) - 1) where m is the current month in UTC. Using
    // DateTime.UtcNow (not DateTime.Now) is load-bearing: the test is
    // supposed to produce the same value on the same calendar day
    // regardless of runner timezone. See docs/sample-benchmark.md.
    [Benchmark]
    public void Benchmark4()
    {
        int month = DateTime.UtcNow.Month;
        double sleepSeconds = 2.15 + ((month % 3) - 1);
        Thread.Sleep((int)(sleepSeconds * 1000));
    }
}
