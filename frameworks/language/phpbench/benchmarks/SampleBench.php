<?php

declare(strict_types=1);

namespace BenchzooSample;

/**
 * Canonical sample benchmark implemented for PHPBench.
 *
 * Each bench method corresponds to one of the four canonical tests in
 * docs/sample-benchmark.md. Method names follow the ``benchX`` pattern,
 * where ``X`` is a camelCase suffix (``Benchmark1`` .. ``Benchmark4``);
 * a parser can map from PHPBench's subject name ``benchBenchmark1`` to
 * ``attributes["test_name"] = "benchmark1"`` by stripping the ``bench``
 * prefix and lower-casing the first character.
 *
 * Annotations are docblock-style (the historical PHPBench idiom, and the
 * form that works unchanged across PHP 7.4..8.x). PHP 8 attribute syntax
 * (``#[Bench]``, ``#[Revs(1)]``, etc.) is also supported by PHPBench 1.3+
 * but is not required.
 *
 * Sleep-heavy tests use ``@Revs(1)`` and ``@Iterations(3)`` to bound wall
 * time — otherwise PHPBench's default calibration would run the 2.15 s
 * sleeps many times over and blow out CI budget.
 */
class SampleBench
{
    private const PAYLOAD_SIZE = 1_400_000;

    /**
     * Sleep-dominated: wall time ~2.15 s.
     *
     * @Revs(1)
     * @Iterations(3)
     * @Groups({"sleep"})
     */
    public function benchBenchmark1(): void
    {
        // usleep takes microseconds; 2.15 s = 2_150_000 us.
        usleep(2_150_000);
    }

    /**
     * Tight CPU loop: counts 0..999 with no body.
     *
     * PHP is interpreted and does not eliminate empty loops, so no
     * ``black_box`` trick is needed. PHPBench will run this many revs
     * per iteration to get a measurable per-rev time.
     *
     * @Revs(1000)
     * @Iterations(5)
     * @Groups({"compute"})
     */
    public function benchBenchmark2(): void
    {
        for ($i = 0; $i < 1000; $i++) {
            // no body
        }
    }

    /**
     * Write 1,400,000 bytes of pseudo-random data to /dev/null.
     *
     * Matches the bash reference's
     * ``head -c 1400000 /dev/urandom > /dev/null``.
     *
     * @Revs(10)
     * @Iterations(5)
     * @Groups({"compute"})
     */
    public function benchBenchmark3(): void
    {
        $data = random_bytes(self::PAYLOAD_SIZE);
        $fh = fopen('/dev/null', 'wb');
        fwrite($fh, $data);
        fclose($fh);
    }

    /**
     * Monthly change-point showcase.
     *
     * Sleep duration in seconds is ``2.15 + ((month % 3) - 1)`` where
     * ``month`` is the current UTC month (1..12). Produces the
     * step-function series described in docs/sample-benchmark.md test 4.
     *
     * @Revs(1)
     * @Iterations(3)
     * @Groups({"sleep"})
     */
    public function benchBenchmark4(): void
    {
        $month = (int) gmdate('n');
        $sleepS = 2.15 + (($month % 3) - 1);
        usleep((int) round($sleepS * 1_000_000));
    }
}
