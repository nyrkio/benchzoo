// Package sample_test implements the canonical benchzoo sample benchmark
// (see docs/sample-benchmark.md) as *regular* Go unit tests — `Test*`
// functions under `go test`, not `Benchmark*` functions under
// `go test -bench`. The per-test wall-clock durations reported by
// gotestsum's JUnit XML output are what the parser consumes.
//
// This is distinct from the `go-test-bench` framework in the sibling
// `frameworks/language/go-test-bench/` directory — that one exercises
// Go's native benchmarking machinery. Here we're using `go test` as a
// timing source in the same spirit as `pytest --junitxml`: the test
// runner is the framework, and per-test duration is the signal.
//
// The test bodies mirror those of go-test-bench's BenchmarkBenchmarkN
// functions, minus the `for i := 0; i < b.N; i++` loop (Test functions
// run exactly once) and the `b.Fatalf` error reporting (swapped for
// `t.Fatalf`).
package sample_test

import (
	"io"
	"math/rand"
	"os"
	"runtime"
	"testing"
	"time"
)

// TestBenchmark1 — sleep-dominated (~2.15 s).
func TestBenchmark1(t *testing.T) {
	time.Sleep(2150 * time.Millisecond)
}

// TestBenchmark2 — tight CPU loop counting 0..1000.
//
// The Go compiler will happily delete a loop with no observable side
// effect. We accumulate into `sum` and hand it to runtime.KeepAlive at
// the end so the optimizer has to treat the loop body as live. This is
// the Go equivalent of std::hint::black_box / JMH's Blackhole.consume.
func TestBenchmark2(t *testing.T) {
	var sum int
	for j := 0; j < 1000; j++ {
		sum += j
	}
	runtime.KeepAlive(sum)
}

// TestBenchmark3 — write 1,400,000 bytes of pseudo-random data to
// /dev/null. math/rand is used deliberately (not crypto/rand) because
// randomness quality is irrelevant and math/rand is substantially
// faster, keeping test 3 in the "small, cheap, deterministic" regime.
func TestBenchmark3(t *testing.T) {
	devnull, err := os.OpenFile("/dev/null", os.O_WRONLY, 0)
	if err != nil {
		t.Fatalf("open /dev/null: %v", err)
	}
	defer devnull.Close()

	r := rand.New(rand.NewSource(1))
	buf := make([]byte, 1_400_000)
	if _, err := r.Read(buf); err != nil {
		t.Fatalf("rand read: %v", err)
	}
	if _, err := io.Copy(devnull, &byteReader{buf: buf}); err != nil {
		t.Fatalf("write /dev/null: %v", err)
	}
}

// byteReader is a trivial io.Reader over an in-memory buffer.
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

// TestBenchmark4 — monthly change-point showcase.
//
// sleep_time = 2.15 + ((m mod 3) - 1) seconds, where m is the current
// UTC month in 1..12. Produces {1.15, 2.15, 3.15} on a 3-month cycle.
func TestBenchmark4(t *testing.T) {
	month := int(time.Now().UTC().Month())
	offset := (month % 3) - 1 // -1, 0, or 1
	sleep := 2150*time.Millisecond + time.Duration(offset)*time.Second
	t.Logf("benchmark4: month=%d, sleep=%s", month, sleep)
	time.Sleep(sleep)
}
