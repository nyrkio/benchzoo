#!/bin/bash
# Build and run the BenchmarkDotNet canonical sample benchmark, then
# capture output in three formats: JSON, CSV, and console text.
#
# BenchmarkDotNet writes its exporter output into
# <artifacts>/results/<Type>-report-full.json and <Type>-report.csv
# (among other files). We redirect artifacts into ./output via
# --artifacts so the build doesn't pollute the project directory with
# a BenchmarkDotNet.Artifacts tree, then copy the reports to
# ./output.json, ./output.csv, and ./output.txt for the workflow
# upload step. The run.sh contract across the benchzoo corpus is "this
# script leaves ./output.<ext> files behind" — that's what the
# workflow's upload-artifact step picks up.
#
# --exporters json csv tells BenchmarkDotNet to emit both JSON and CSV
# output. The JsonExporterAttribute.Full and CsvExporter attributes on
# the benchmark class control the specific variants emitted. Console
# output is also tee'd to ./output.txt for a third capture format.
set -euo pipefail

cd "$(dirname "$0")"

rm -rf ./output ./output.json ./output.csv ./output.txt

dotnet run -c Release --project SampleBenchmark.csproj -- \
    --exporters json csv \
    --artifacts ./output \
    2>&1 | tee ./output.txt

# BenchmarkDotNet names reports after the benchmark type. There should
# be exactly one of each under output/results/.
JSON_REPORT=$(ls ./output/results/*-report-full.json | head -n 1)
cp "$JSON_REPORT" ./output.json

CSV_REPORT=$(ls ./output/results/*-report.csv | head -n 1)
cp "$CSV_REPORT" ./output.csv
