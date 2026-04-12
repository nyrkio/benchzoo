package io.nyrkio.benchzoo.junit;

import org.junit.jupiter.api.Test;

import java.io.FileOutputStream;
import java.io.IOException;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.util.Random;

/**
 * Raw JUnit 5 implementation of the canonical benchzoo sample benchmark.
 *
 * <p>Four plain {@code @Test} methods — no JMH, no AssertJ benchmarking,
 * no pytest-benchmark-style timing extension. The JUnit test runner
 * (driven by Maven Surefire) records per-test wall-clock duration in its
 * junit XML output regardless, and that duration is what benchzoo's
 * {@code junit_vanilla} parser consumes.
 *
 * <p>See {@code docs/sample-benchmark.md} for the spec. Test method
 * names (benchmark1..benchmark4) are kept identical to the canonical
 * names so the parser can use them directly as
 * {@code attributes["test_name"]} with no normalization.
 */
public class SampleTest {

    /**
     * Seeded RNG for benchmark3, to keep the random payload deterministic
     * run-to-run. The actual byte values do not matter for wall-clock
     * measurement, but a fixed seed makes differential debugging easier.
     */
    private final Random random = new Random(42);

    /** Test 1 — sleep-dominated (~2.15 s). */
    @Test
    public void benchmark1() throws InterruptedException {
        Thread.sleep(2150);
    }

    /**
     * Test 2 — tight CPU loop, sub-millisecond.
     *
     * <p>Unlike the JMH implementation, there is no {@code Blackhole} to
     * defeat dead-code elimination here. JUnit tests are not run under
     * a benchmark harness; the JIT is free to prove the loop has no
     * observable side effects and delete it. We accept that: test 2's
     * role in the corpus is to exercise sub-millisecond measurement
     * handling in the parser, not to produce a physically meaningful
     * loop time. A volatile sink keeps the loop from being trivially
     * hoisted to a constant.
     */
    @Test
    public void benchmark2() {
        int sink = 0;
        for (int i = 0; i < 1000; i++) {
            sink += i;
        }
        // Use the value so the compiler can't prove it's dead.
        if (sink == Integer.MIN_VALUE) {
            throw new AssertionError("unreachable");
        }
    }

    /** Test 3 — write 1.4 MB of pseudo-random data to /dev/null. */
    @Test
    public void benchmark3() throws IOException {
        byte[] payload = new byte[1_400_000];
        random.nextBytes(payload);
        try (FileOutputStream out = new FileOutputStream("/dev/null")) {
            out.write(payload);
        }
    }

    /**
     * Test 4 — monthly change-point showcase. Sleeps for
     * {@code 2.15 + ((month mod 3) - 1)} seconds, where {@code month}
     * is the current UTC month. See {@code docs/sample-benchmark.md}
     * for the formula table.
     */
    @Test
    public void benchmark4() throws InterruptedException {
        int month = ZonedDateTime.now(ZoneOffset.UTC).getMonthValue();
        long sleepMillis = (long) ((2.15 + (month % 3 - 1)) * 1000);
        Thread.sleep(sleepMillis);
    }
}
