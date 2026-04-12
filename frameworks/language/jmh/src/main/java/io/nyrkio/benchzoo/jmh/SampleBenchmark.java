package io.nyrkio.benchzoo.jmh;

import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Fork;
import org.openjdk.jmh.annotations.Measurement;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.Warmup;
import org.openjdk.jmh.infra.Blackhole;

import java.io.FileOutputStream;
import java.io.IOException;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.util.Random;
import java.util.concurrent.TimeUnit;

/**
 * JMH implementation of the canonical benchzoo sample benchmark.
 *
 * <p>See {@code docs/sample-benchmark.md} for the spec. Four @Benchmark
 * methods — {@code benchmark1}..{@code benchmark4} — mirror the four
 * canonical tests. JMH emits one entry per @Benchmark method in its JSON
 * output, keyed by the fully-qualified name
 * {@code io.nyrkio.benchzoo.jmh.SampleBenchmark.benchmarkN}; the parser
 * is expected to strip the class prefix and use the short
 * {@code benchmarkN} as {@code attributes["test_name"]}.
 *
 * <h2>Run-time trade-off</h2>
 *
 * Class-level {@code @Warmup(iterations = 1, time = 1)},
 * {@code @Measurement(iterations = 3, time = 1)}, and {@code @Fork(1)}
 * are deliberately modest so the whole suite finishes in a few minutes
 * of CI wall time.
 *
 * <p>JMH's {@code time} attribute on {@code @Measurement}/{@code @Warmup}
 * is the <em>target batch duration</em>: JMH repeatedly invokes the
 * benchmark method until roughly {@code time} seconds have elapsed, then
 * treats that as one measurement iteration. For the sub-millisecond
 * {@code benchmark2} this produces millions of invocations per iteration,
 * which is exactly what you want for statistical stability. For the
 * sleep-heavy {@code benchmark1} and {@code benchmark4} this is the
 * <em>opposite</em> of what you want: a ~2.15s sleep easily overshoots
 * the 1s target, JMH reacts by running a single invocation per
 * iteration, and the measurement iteration still takes ~2.15 s. Over 3
 * iterations × 1 fork that's ~6.5 s per sleep benchmark, plus 1 warmup
 * iteration. Total suite wall time is on the order of a minute, which
 * is acceptable for CI.
 *
 * <p>We considered overriding {@code @Measurement(iterations = 1)} per
 * sleep method to shave seconds off the run, but chose to keep a uniform
 * 3-iteration measurement across all four benchmarks: the fixture stays
 * easier to reason about (same {@code measurementIterations} in every
 * JSON entry), and the ground-truth assertion on {@code benchmark1}'s
 * mean is slightly more robust with three samples than with one.
 */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@Warmup(iterations = 1, time = 1)
@Measurement(iterations = 3, time = 1)
@Fork(1)
@State(Scope.Benchmark)
public class SampleBenchmark {

    /**
     * Seeded RNG for benchmark3, to keep the random payload deterministic
     * run-to-run. The actual byte values do not matter for wall-clock
     * measurement, but a fixed seed makes differential debugging easier.
     */
    private final Random random = new Random(42);

    /**
     * Pre-allocated 1,400,000-byte scratch buffer for benchmark3. We fill
     * it fresh on each invocation via {@link Random#nextBytes(byte[])},
     * so the "random data" is regenerated per call but the allocation
     * cost is kept out of the measured path.
     */
    private final byte[] payload = new byte[1_400_000];

    /**
     * Test 1 — sleep-dominated (~2.15 s).
     *
     * <p>{@code Thread.sleep(2150)} throws {@link InterruptedException},
     * which JMH allows benchmark methods to declare.
     */
    @Benchmark
    public void benchmark1() throws InterruptedException {
        Thread.sleep(2150);
    }

    /**
     * Test 2 — tight CPU loop, sub-millisecond.
     *
     * <p>{@link Blackhole#consume(int)} is <strong>mandatory</strong>
     * here. Without it, HotSpot's JIT trivially proves the loop has no
     * observable side effects and eliminates it entirely, which would
     * make this benchmark measure "return from an empty method" rather
     * than "execute 1000 loop iterations." The Blackhole API exists
     * specifically to defeat dead-code elimination in JMH benchmarks;
     * see the JMH samples for the canonical rationale.
     */
    @Benchmark
    public void benchmark2(Blackhole blackhole) {
        for (int i = 0; i < 1000; i++) {
            blackhole.consume(i);
        }
    }

    /**
     * Test 3 — write 1.4 MB of pseudo-random data to /dev/null.
     *
     * <p>Uses a {@link FileOutputStream} opened on {@code /dev/null}.
     * The buffer is filled via {@link Random#nextBytes(byte[])} inside
     * the measured path so the RNG work is part of the benchmark (same
     * as the other language implementations, where generating the
     * random bytes is not separated from writing them). The stream is
     * closed in a try-with-resources so we don't leak file descriptors
     * across JMH invocations.
     */
    @Benchmark
    public void benchmark3(Blackhole blackhole) throws IOException {
        random.nextBytes(payload);
        try (FileOutputStream out = new FileOutputStream("/dev/null")) {
            out.write(payload);
        }
        blackhole.consume(payload);
    }

    /**
     * Test 4 — monthly change-point showcase. Sleeps for
     * {@code 2.15 + ((month mod 3) - 1)} seconds, where {@code month}
     * is the current UTC month. See
     * {@code docs/sample-benchmark.md} for the formula table.
     */
    @Benchmark
    public void benchmark4() throws InterruptedException {
        int month = ZonedDateTime.now(ZoneOffset.UTC).getMonthValue();
        long sleepMillis = (long) ((2.15 + (month % 3 - 1)) * 1000);
        Thread.sleep(sleepMillis);
    }
}
