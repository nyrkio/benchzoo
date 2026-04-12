#!/bin/bash
# Generate a small synthetic dataset (10,000 rows of TSV) that matches
# the trimmed `hits` schema in schema.sql, and load it into ClickHouse.
# Upstream ClickBench loads a 70 GB real-traffic dump; we load ~500 KB
# of synthetic data because the point of this fixture is to capture the
# ClickBench JSON result format, not to reproduce ClickBench's numbers.
set -euo pipefail
cd "$(dirname "$0")"

: "${CLICKHOUSE_HOST:=localhost}"
CH="clickhouse-client --host=${CLICKHOUSE_HOST}"

$CH --multiquery < schema.sql

python3 - > hits.tsv <<'PY'
import random
random.seed(42)
urls = ["http://example.com/a", "http://example.com/b", "http://foo.test/x",
        "http://foo.test/y", "http://bar.test/z"]
titles = ["News", "Sports", "Weather", "Tech", "Shop"]
for i in range(10000):
    print("\t".join(str(x) for x in [
        i, "2024-01-%02d" % (1 + i % 28), "2024-01-01 12:00:00",
        random.randint(1, 1000), random.randint(1, 50),
        random.choice(urls), random.choice(titles),
        random.randint(1, 200), i % 2, random.choice([1024, 1280, 1920]),
    ]))
PY

$CH --query="INSERT INTO hits FORMAT TSV" < hits.tsv
$CH --query="SELECT count() FROM hits"
