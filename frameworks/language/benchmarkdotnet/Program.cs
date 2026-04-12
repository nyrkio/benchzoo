// Entry point for the BenchmarkDotNet canonical sample benchmark.
//
// BenchmarkDotNet is driven via BenchmarkRunner. All exporter / job /
// diagnoser configuration lives as attributes on the SampleBenchmark
// class itself (see SampleBenchmark.cs) so the runner call stays a
// one-liner. This mirrors BenchmarkDotNet's own "getting started"
// idiom and keeps Program.cs from drifting into config duplication.

using BenchmarkDotNet.Running;
using BenchzooSample;

BenchmarkRunner.Run<SampleBenchmark>();
