// Package sample_benchmark implements the canonical benchzoo sample
// benchmark (see docs/sample-benchmark.md) using Go's standard library
// testing.B support — i.e. `go test -bench`.
//
// Go's benchmarking model re-runs the benchmarked body b.N times, where
// b.N is auto-calibrated by the framework to hit a target wall time
// (1 s by default). That model is a poor fit for the canonical suite:
// tests 1 and 4 sleep for multi-second fixed durations, and we want
// exactly one iteration of those — not "however many fit in the target
// window." run.sh therefore passes `-benchtime=1x`, which pins b.N=1
// for every benchmark in this file. The inner `for i := 0; i < b.N; i++`
// loop still has to be present (it's the shape `go test -bench`
// expects), but in practice it runs exactly once per benchmark.
package sample_benchmark

import (
	"io"
	"math/rand"
	"os"
	"runtime"
	"testing"
	"time"
)

// BenchmarkBenchmark1 — sleep-dominated (~2.15 s).
//
// With -benchtime=1x the body runs once and reports ~2.15e9 ns/op.
func BenchmarkBenchmark1(b *testing.B) {
	for i := 0; i < b.N; i++ {
		time.Sleep(2150 * time.Millisecond)
	}
}

// BenchmarkBenchmark2 — tight CPU loop counting 0..1000.
//
// The Go compiler will happily delete a loop with no observable side
// effect. We accumulate into `sum` and hand it to runtime.KeepAlive at
// the end so the optimizer has to treat the loop body as live. This is
// the Go equivalent of std::hint::black_box / JMH's Blackhole.consume.
//
// (Go 1.24 introduces b.Loop() which removes a lot of this ceremony,
// but we pin Go 1.22 for now so we stick with the KeepAlive idiom.)
func BenchmarkBenchmark2(b *testing.B) {
	var sum int
	for i := 0; i < b.N; i++ {
		for j := 0; j < 1000; j++ {
			sum += j
		}
	}
	runtime.KeepAlive(sum)
}

// BenchmarkBenchmark3 — write 1,400,000 bytes of pseudo-random data
// to /dev/null.
//
// math/rand is used deliberately (not crypto/rand): randomness quality
// is irrelevant here and math/rand is substantially faster, which keeps
// test 3 in the "small, cheap, deterministic" regime the spec calls for.
func BenchmarkBenchmark3(b *testing.B) {
	devnull, err := os.OpenFile("/dev/null", os.O_WRONLY, 0)
	if err != nil {
		b.Fatalf("open /dev/null: %v", err)
	}
	defer devnull.Close()

	// Seed deterministically so runs are reproducible across hosts.
	r := rand.New(rand.NewSource(1))
	buf := make([]byte, 1_400_000)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		if _, err := r.Read(buf); err != nil {
			b.Fatalf("rand read: %v", err)
		}
		if _, err := io.Copy(devnull, &byteReader{buf: buf}); err != nil {
			b.Fatalf("write /dev/null: %v", err)
		}
	}
}

// byteReader is a trivial io.Reader over an in-memory buffer. We use
// io.Copy rather than devnull.Write(buf) directly only to exercise a
// shape closer to a real streaming write; the end result is the same
// 1,400,000 bytes hitting /dev/null per iteration.
type byteReader struct {
	buf []byte
	pos int
}

func (r *byteReader) Read(p []byte) (int, error) {
	if r.pos >= len(r.buf) {
		return 0, io.EOF
	}
	n := copy(p, r.buf[r.pos:])
	r.pos += n
	return n, nil
}

// BenchmarkBenchmark4 — monthly change-point showcase.
//
// sleep_time = 2.15 + ((m mod 3) - 1) seconds, where m is the current
// UTC month in 1..12. Produces {1.15, 2.15, 3.15} on a 3-month cycle.
func BenchmarkBenchmark4(b *testing.B) {
	month := int(time.Now().UTC().Month())
	offset := (month % 3) - 1 // -1, 0, or 1
	sleep := 2150*time.Millisecond + time.Duration(offset)*time.Second
	b.Logf("benchmark4: month=%d, sleep=%s", month, sleep)

	for i := 0; i < b.N; i++ {
		time.Sleep(sleep)
	}
}
