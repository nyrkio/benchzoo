// Canonical benchzoo sample benchmark, `cargo bench` (libtest) edition.
//
// This uses Rust's original built-in benchmarking harness, accessed via
// the unstable `test` crate. It predates criterion and is still widely
// used for small microbenchmarks inside rustc itself and in crates that
// don't want a criterion dependency.
//
// NIGHTLY REQUIRED. `#![feature(test)]` and `extern crate test;` are
// both nightly-only. See `rust-toolchain.toml` in this directory for the
// pinned nightly version.
//
// Output format, for one line per `#[bench]` fn:
//
//   test benchmark1 ... bench:  2150123486 ns/iter (+/- 10172)
//
// This is **byte-identical** to criterion's `--output-format bencher`,
// so the benchzoo parser can be shared between the two.
//
// Notes on libtest's Bencher for sleep-dominated tests:
//
// `test::Bencher` is designed for microbenchmarks — it picks the number
// of iterations adaptively so that a measurement run takes roughly
// 1 second. For a closure that sleeps 2.15 s, libtest will run the
// closure once, measure ~2.15 s, and move on. The reported "ns/iter"
// will simply be ~2_150_000_000. This is fine for benchzoo's purposes
// (we just want the wall time to show up somewhere in the output), but
// it means the statistical quality of the measurement is poor: there's
// effectively one sample. That's an accepted limitation of libtest for
// this category of bench. Criterion deals with it better via explicit
// `sample_size` control; libtest does not expose any equivalent knob.

#![feature(test)]

extern crate test;

use std::hint::black_box as std_black_box;
use std::io::Write;
use std::thread;
use std::time::Duration;

use chrono::{Datelike, Utc};
use test::Bencher;

// ---------------------------------------------------------------------------
// Test 1 — sleep 2.15 s.
//
// libtest runs this essentially once (see module-level note). The reported
// ns/iter will be ~2_150_000_000 with a large deviation because there's
// no real sample spread to speak of.
// ---------------------------------------------------------------------------
#[bench]
fn benchmark1(b: &mut Bencher) {
    b.iter(|| {
        thread::sleep(Duration::from_millis(2150));
    });
}

// ---------------------------------------------------------------------------
// Test 2 — tight CPU loop, sub-microsecond.
//
// Same as the criterion sibling: rustc will delete an empty
// `for i in 0..1000 {}` loop entirely. `test::black_box` is libtest's
// "don't optimize this away" primitive — semantically identical to
// `std::hint::black_box`, just exposed via the test crate. Either works
// under nightly; we use `test::black_box` here to lean into the libtest
// idiom (and to demonstrate that the test crate carries its own copy).
// ---------------------------------------------------------------------------
#[bench]
fn benchmark2(b: &mut Bencher) {
    b.iter(|| {
        for i in 0..1000u32 {
            test::black_box(i);
        }
    });
}

// ---------------------------------------------------------------------------
// Test 3 — write 1.4 MB to a sink.
//
// 1_400_000 is decimal MB as specified in docs/sample-benchmark.md
// (not MiB). The buffer is zero-filled rather than pseudo-random:
// std::io::sink() discards its input without inspecting it, so the
// byte values are immaterial and we avoid pulling in `rand` as a
// dev-dependency. `std_black_box` here just defends against the
// compiler noticing that the buffer is never read after the write.
// ---------------------------------------------------------------------------
#[bench]
fn benchmark3(b: &mut Bencher) {
    let buf = vec![0u8; 1_400_000];
    b.iter(|| {
        let mut sink = std::io::sink();
        sink.write_all(std_black_box(&buf)).unwrap();
    });
}

// ---------------------------------------------------------------------------
// Test 4 — monthly change-point showcase.
//
// sleep_time = 2.15 + ((m mod 3) - 1), with m = current UTC month (1..12).
// chrono handles the calendar math. The month is read once before the
// bench loop so every iteration in a single run uses the same value —
// the "change point" emerges across runs, not within a single run.
//
// Like benchmark1, libtest will effectively run this once and report
// a single ~2.15 s / ~1.15 s / ~3.15 s measurement depending on the
// current UTC month.
// ---------------------------------------------------------------------------
#[bench]
fn benchmark4(b: &mut Bencher) {
    let month = Utc::now().month() as i32; // 1..=12
    let offset = (month % 3) - 1; // -1, 0, or 1
    let sleep_s = 2.15f64 + offset as f64;
    let sleep_dur = Duration::from_secs_f64(sleep_s);

    b.iter(|| {
        thread::sleep(sleep_dur);
    });
}
