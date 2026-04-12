-- Five representative ClickBench-style queries, adapted to the trimmed
-- `hits` schema in schema.sql. Query shapes mirror the canonical 43 in
-- https://github.com/ClickHouse/ClickBench/blob/main/clickhouse/queries.sql
-- (Q0 count, Q1 filtered count, Q5 distinct users, Q7 top-N group by,
-- Q20 URL prefix filter). One query per line: run.sh iterates the file.
SELECT count(*) FROM hits;
SELECT count(*) FROM hits WHERE IsMobile = 1;
SELECT count(DISTINCT UserID) FROM hits;
SELECT RegionID, count(*) AS c FROM hits GROUP BY RegionID ORDER BY c DESC LIMIT 10;
SELECT Title, avg(ResolutionWidth) FROM hits WHERE URL LIKE 'http://example.com/%' GROUP BY Title ORDER BY Title;
