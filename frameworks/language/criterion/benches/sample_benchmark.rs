// Canonical benchzoo sample benchmark, criterion edition.
//
// Four benches, one per test in docs/sample-benchmark.md. Each bench is
// registered under the literal name "benchmark1".."benchmark4" so the
// parser can map `target/criterion/<name>/new/estimates.json` directly
// to `attributes["test_name"]`.
//
// We use two criterion groups so test 1 and test 4 (both sleep-dominated,
// ~2.15 s per iteration) can run with a reduced sample_size. The default
// sample_size of 100 would mean ~215 seconds per bench — multiply by two
// and the warmup and CI minutes dominate. sample_size(10) is the minimum
// criterion accepts and gives us 10 * 2.15 s ≈ 22 s per bench, which is
// plenty to exercise the output format. The tradeoff — wider confidence
// intervals on the mean — is acceptable because the sleep is deterministic
// and the parser layer does not care about statistical tightness here.
//
// Tests 2 and 3 run with the default configuration. Test 2 is the
// sub-microsecond CPU loop where criterion's default 100-sample, ~5 s
// measurement plan is exactly what we want. Test 3 writes 1.4 MB to
// std::io::sink() — `sink()` is portable and the sample-benchmark spec
// explicitly notes /dev/null is a proxy for "cheap deterministic write",
// not a real I/O test.

use std::hint::black_box;
use std::io::Write;
use std::thread;
use std::time::Duration;

use chrono::{Datelike, Utc};
use criterion::{criterion_group, criterion_main, Criterion};

// ---------------------------------------------------------------------------
// Test 1 — sleep 2.15 s.
// ---------------------------------------------------------------------------
fn bench_benchmark1(c: &mut Criterion) {
    c.bench_function("benchmark1", |b| {
        b.iter(|| {
            thread::sleep(Duration::from_millis(2150));
        });
    });
}

// ---------------------------------------------------------------------------
// Test 2 — tight CPU loop, sub-microsecond.
//
// The Rust compiler *will* delete an empty `for i in 0..1000 {}` loop
// entirely. `std::hint::black_box` is the idiomatic "don't optimize this
// away" primitive and is mandatory here — without it this bench measures
// nothing. This is exactly the case docs/sample-benchmark.md calls out
// in its "Note on optimization" for test 2.
// ---------------------------------------------------------------------------
fn bench_benchmark2(c: &mut Criterion) {
    c.bench_function("benchmark2", |b| {
        b.iter(|| {
            for i in 0..1000u32 {
                black_box(i);
            }
        });
    });
}

// ---------------------------------------------------------------------------
// Test 3 — write 1.4 MB to a sink.
//
// The spec calls for "1.4 MB of pseudo-random data". We fill the buffer
// with zeros rather than pulling in a `rand` dev-dependency:
// std::io::sink() discards its input without inspecting the contents, so
// the byte values are immaterial to what this test exercises (a 1.4 MB
// write of a non-round size). Keeping the dev-dependency list minimal
// keeps CI cold-build time down and makes the Cargo.toml easier to read.
//
// 1_400_000 is decimal MB as specified (not MiB).
// ---------------------------------------------------------------------------
fn bench_benchmark3(c: &mut Criterion) {
    let buf = vec![0u8; 1_400_000];
    c.bench_function("benchmark3", |b| {
        b.iter(|| {
            let mut sink = std::io::sink();
            sink.write_all(black_box(&buf)).unwrap();
        });
    });
}

// ---------------------------------------------------------------------------
// Test 4 — monthly change-point showcase.
//
// sleep_time = 2.15 + ((m mod 3) - 1), with m = current UTC month (1..12).
// chrono gives us the UTC month without having to do epoch-to-calendar
// math by hand. The month is read once before the bench loop so every
// iteration in a single run uses the same value — the "change point"
// emerges across runs, not within a single run.
// ---------------------------------------------------------------------------
fn bench_benchmark4(c: &mut Criterion) {
    let month = Utc::now().month() as i32; // 1..=12
    let offset = (month % 3) - 1; // -1, 0, or 1
    let sleep_s = 2.15f64 + offset as f64;
    let sleep_dur = Duration::from_secs_f64(sleep_s);

    c.bench_function("benchmark4", |b| {
        b.iter(|| {
            thread::sleep(sleep_dur);
        });
    });
}

// ---------------------------------------------------------------------------
// Groups.
// ---------------------------------------------------------------------------

// Sleep-heavy group: reduce sample_size to the criterion minimum (10)
// so the whole bench run finishes in tens of seconds rather than hundreds.
fn sleepy_config() -> Criterion {
    Criterion::default().sample_size(10)
}

criterion_group! {
    name = sleepy;
    config = sleepy_config();
    targets = bench_benchmark1, bench_benchmark4
}

criterion_group!(fast, bench_benchmark2, bench_benchmark3);

criterion_main!(fast, sleepy);
