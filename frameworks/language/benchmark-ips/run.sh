#!/usr/bin/env bash
# Run the canonical sample benchmark under benchmark-ips and capture both
# the hand-rolled JSON (output.json), benchmark-ips's native Marshal dump
# (output-raw.dump), and the pretty-printed console output (output.txt).
#
# The console output (benchmark-ips's default human-readable table plus
# the `compare!` ranking block) is itself a common thing real users paste
# into issues / PR descriptions, so a text-format parser for it is worth
# having later — hence capturing it explicitly.

set -euo pipefail

bundle install
bundle exec ruby bench.rb 2>&1 | tee output.txt
