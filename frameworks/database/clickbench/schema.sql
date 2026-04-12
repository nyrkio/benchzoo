-- Minimal ClickBench-shaped schema for benchzoo.
--
-- The upstream ClickBench "hits" table at
-- https://github.com/ClickHouse/ClickBench/blob/main/clickhouse/create.sql
-- defines ~100 columns against a 70 GB TSV dump. We do not want to
-- download 70 GB in CI, so this is a deliberately trimmed ~10-column
-- subset that still exercises the ClickBench-style query shapes
-- (GROUP BY, WHERE filters, counts, aggregations over URL-like text).
-- The column names are kept identical to the upstream schema so the
-- query bodies in queries.sql read the same as the canonical ones.
CREATE TABLE IF NOT EXISTS hits
(
    WatchID         UInt64,
    EventDate       Date,
    EventTime       DateTime,
    UserID          UInt64,
    CounterID       UInt32,
    URL             String,
    Title           String,
    RegionID        UInt32,
    IsMobile        UInt8,
    ResolutionWidth UInt16
)
ENGINE = MergeTree
ORDER BY (CounterID, EventDate, UserID);
