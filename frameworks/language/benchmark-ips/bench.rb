# Canonical sample benchmark implemented for benchmark-ips (Ruby).
#
# Each x.report(...) block corresponds to one of the four canonical tests
# in docs/sample-benchmark.md. The label passed to report() is chosen so
# a parser can map directly to attributes["test_name"] (e.g. "benchmark1").
#
# benchmark-ips is iterations-per-second oriented: it calibrates the inner
# iteration count so each measurement window (config :time seconds) yields
# a stable ips number. For the sleep-dominated tests (1 and 4) this means
# only 1-2 iterations per window, and the headline "ips" value is small
# (e.g. ~0.47 for a 2.15 s sleep). The parser should convert ips to
# seconds-per-iteration as 1/ips when the downstream metric of interest
# is wall time.
#
# JSON emission
# -------------
# benchmark-ips does not ship a clean, documented JSON output format out
# of the box. Recent versions expose a `json!` helper that writes
# per-report stats, but its schema is not officially stable. To keep the
# captured fixture self-describing and version-independent, this script
# ALSO emits a hand-rolled `output.json` built from each report's public
# attributes (label, ips, stddev, microseconds_per_i, iterations). The
# `x.save!` native dump is kept too for reference / alternate parsing.

require 'benchmark/ips'
require 'json'
require 'date'
require 'securerandom'

month = Time.now.utc.month
sleep_time_4 = 2.15 + ((month % 3) - 1)

PAYLOAD_SIZE = 1_400_000

report = Benchmark.ips do |x|
  # Bound wall time per benchmark. Default is 5 s measurement + 2 s warmup;
  # we trim it so the four tests (including two ~2.15 s sleeps) complete
  # in reasonable CI time.
  x.config(time: 2, warmup: 1)

  x.report("benchmark1") { sleep(2.15) }

  x.report("benchmark2") do
    sum = 0
    1000.times { |i| sum += i }
    sum
  end

  x.report("benchmark3") do
    data = SecureRandom.random_bytes(PAYLOAD_SIZE)
    File.open("/dev/null", "wb") { |f| f.write(data) }
  end

  x.report("benchmark4") { sleep(sleep_time_4) }

  # Native benchmark-ips dump (Marshal-based). Not JSON; captured so
  # downstream can decide whether a parser against the raw dump is
  # valuable.
  x.save! "output-raw.dump"

  x.compare!
  x.hold! "output-raw.dump"
end

# Hand-rolled JSON emission. `report.entries` is the list of Report::Entry
# objects; each has the public accessors used below.
payload = {
  "benchmark_ips_version" => Benchmark::IPS::VERSION,
  "ruby_version" => RUBY_VERSION,
  "ruby_platform" => RUBY_PLATFORM,
  "config" => { "time" => 2, "warmup" => 1 },
  "month_utc" => month,
  "benchmark4_sleep_s" => sleep_time_4,
  "benchmarks" => report.entries.map do |entry|
    {
      "name" => entry.label,
      "ips" => entry.ips,
      "ips_stddev" => entry.ips_sd,
      "microseconds_per_iteration" => entry.microseconds,
      "seconds_per_iteration" => (entry.ips.zero? ? nil : 1.0 / entry.ips),
      "iterations" => entry.iterations,
      "measurement_cycle" => (entry.respond_to?(:measurement_cycle) ? entry.measurement_cycle : nil),
      "stats_class" => entry.stats.class.name,
    }
  end,
}

File.write("output.json", JSON.pretty_generate(payload))
