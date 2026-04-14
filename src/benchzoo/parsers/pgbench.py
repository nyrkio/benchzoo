"""Parser for pgbench text output.

pgbench emits a plain-text report per invocation. benchzoo's corpus
runs pgbench four separate times (once per ``benchmarkN.sql``) and
``run.sh`` concatenates the outputs with ``=== benchmarkN ===``
separator lines, yielding a single ``output.txt`` with four blocks.

A single block looks roughly like::

    transaction type: benchmark1.sql
    scaling factor: 1
    query mode: simple
    number of clients: 1
    number of threads: 1
    number of transactions per client: 1
    number of transactions actually processed: 1/1
    latency average = 2150.342 ms
    tps = 0.465 (including connections establishing)
    tps = 0.468 (excluding connections establishing)

Real pgbench 16 captures use a slightly different shape for the TPS
summary — they emit a single ``tps = ... (without initial connection
time)`` line plus a separate ``initial connection time = ... ms`` line.
The parser accepts either shape.

See ``frameworks/database/pgbench/README.md`` for the parser notes
this implementation follows.
"""

from __future__ import annotations

import re


_SEPARATOR_RE = re.compile(r"^===\s*(\S+)\s*===\s*$", re.MULTILINE)

# Metric lines.
_LATENCY_RE = re.compile(r"^latency average\s*=\s*([0-9.]+)\s*ms", re.MULTILINE)
_TPS_INCL_RE = re.compile(
    r"^tps\s*=\s*([0-9.]+)\s*\(including connections establishing\)", re.MULTILINE
)
_TPS_EXCL_RE = re.compile(
    r"^tps\s*=\s*([0-9.]+)\s*\(excluding connections establishing\)", re.MULTILINE
)
_TPS_WITHOUT_INITIAL_RE = re.compile(
    r"^tps\s*=\s*([0-9.]+)\s*\(without initial connection time\)", re.MULTILINE
)
_ANY_TPS_RE = re.compile(r"^tps\s*=\s*([0-9.]+)", re.MULTILINE)

# Header → extra_info.
_TRANSACTION_TYPE_RE = re.compile(r"^transaction type:\s*(.+?)\s*$", re.MULTILINE)
_SCALING_RE = re.compile(r"^scaling factor:\s*(\S+)", re.MULTILINE)
_CLIENTS_RE = re.compile(r"^number of clients:\s*(\d+)", re.MULTILINE)
_THREADS_RE = re.compile(r"^number of threads:\s*(\d+)", re.MULTILINE)
_MODE_RE = re.compile(r"^query mode:\s*(\S+)", re.MULTILINE)
_TX_PER_CLIENT_RE = re.compile(
    r"^number of transactions per client:\s*(\d+)", re.MULTILINE
)
_TX_PROCESSED_RE = re.compile(
    r"^number of transactions actually processed:\s*(.+?)\s*$", re.MULTILINE
)
_INITIAL_CONN_RE = re.compile(
    r"^initial connection time\s*=\s*([0-9.]+)\s*ms", re.MULTILINE
)


def _split_blocks(text: str) -> list[tuple[str, str]]:
    """Split ``text`` on ``=== benchmarkN ===`` markers.

    Returns a list of ``(marker_name, block_body)`` tuples in order.
    """
    matches = list(_SEPARATOR_RE.finditer(text))
    blocks: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        blocks.append((m.group(1), text[start:end]))
    return blocks


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    out: list[dict] = []
    for marker_name, block in _split_blocks(content):
        # Prefer the transaction-type line for test_name; fall back to
        # the separator marker.
        tx_match = _TRANSACTION_TYPE_RE.search(block)
        if tx_match:
            tx = tx_match.group(1).strip()
            if tx.endswith(".sql"):
                tx = tx[: -len(".sql")]
            test_name = tx
        else:
            test_name = marker_name

        metrics: list[dict] = []
        passed = True

        lat = _LATENCY_RE.search(block)
        if lat:
            metrics.append({
                "name": "latency_average",
                "unit": "ms",
                "value": float(lat.group(1)),
                "direction": "lower_is_better",
            })
        else:
            passed = False

        tps_incl = _TPS_INCL_RE.search(block)
        tps_excl = _TPS_EXCL_RE.search(block)
        tps_without_initial = _TPS_WITHOUT_INITIAL_RE.search(block)

        if tps_incl:
            metrics.append({
                "name": "tps_including_connections",
                "unit": "ops/s",
                "value": float(tps_incl.group(1)),
                "direction": "higher_is_better",
            })
        if tps_excl:
            metrics.append({
                "name": "tps_excluding_connections",
                "unit": "ops/s",
                "value": float(tps_excl.group(1)),
                "direction": "higher_is_better",
            })
        if tps_without_initial:
            # pgbench 16 "without initial connection time" is
            # semantically equivalent to the older "excluding connections
            # establishing" — record it under both conventional names so
            # downstream consumers see a stable shape across versions.
            value = float(tps_without_initial.group(1))
            metrics.append({
                "name": "tps_excluding_connections",
                "unit": "ops/s",
                "value": value,
                "direction": "higher_is_better",
            })

        if not (tps_incl or tps_excl or tps_without_initial):
            passed = False

        # Fallback: if none of the tagged tps lines matched but an
        # un-annotated ``tps = X`` line exists, at least record it so
        # the result isn't empty.
        if not metrics and _ANY_TPS_RE.search(block):
            metrics.append({
                "name": "tps",
                "unit": "ops/s",
                "value": float(_ANY_TPS_RE.search(block).group(1)),
                "direction": "higher_is_better",
            })

        params: dict = {}
        extra_info: dict = {}
        if (m := _SCALING_RE.search(block)):
            try:
                params["scaling_factor"] = int(m.group(1))
            except ValueError:
                params["scaling_factor"] = m.group(1)
        if (m := _CLIENTS_RE.search(block)):
            params["clients"] = int(m.group(1))
        if (m := _THREADS_RE.search(block)):
            params["threads"] = int(m.group(1))
        if (m := _MODE_RE.search(block)):
            params["query_mode"] = m.group(1)
        if (m := _TX_PER_CLIENT_RE.search(block)):
            params["transactions_per_client"] = int(m.group(1))
        if (m := _TX_PROCESSED_RE.search(block)):
            extra_info["transactions_processed"] = m.group(1).strip()
        if (m := _INITIAL_CONN_RE.search(block)):
            extra_info["initial_connection_time_ms"] = float(m.group(1))

        test: dict = {"test_name": test_name}
        if params:
            test["params"] = params
        result: dict = {
            "test": test,
            "run": {"passed": passed},
            "env": {"framework": {"name": "pgbench"}},
            "metrics": metrics,
        }
        if extra_info:
            result["extra_info"] = extra_info
        out.append(result)

    return out
