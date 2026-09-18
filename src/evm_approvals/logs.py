"""Fetch Approval / ApprovalForAll logs across a block span. Public RPCs cap
eth_getLogs differently, so windows are split and shrunk on a range complaint
and transient errors are retried with backoff."""

from __future__ import annotations

import time

from eth_utils import to_checksum_address

# A getLogs call is rejected for two reasons that both mean "ask for less":
# too many matched results, or too wide a block range. Providers word it
# differently, so match on fragments seen across Alchemy, Infura, Ankr,
# QuickNode, Cloudflare, BlockPI, Llama and go-ethereum.
_RANGE_MARKERS = (
    "block range",
    "range is too large",
    "range too large",
    "too large",
    "too wide",
    "too many results",
    "more than 10000 results",
    "query returned more than",
    "response size exceeded",
    "limited to",
    "up to a",
    "limit exceeded",
    "logs matched by query exceeds",
    "please limit",
    "query timeout",
)


class RpcRangeError(Exception):
    """The node refused the block range or result set; narrow and retry."""


def is_range_error(message: str) -> bool:
    text = message.lower()
    return any(marker in text for marker in _RANGE_MARKERS)


def fetch_logs(fetcher, from_block, to_block, block_range=10000,
               max_retries=5, base_delay=0.5, min_range=1, sleep=time.sleep):
    """Pull logs from from_block..to_block inclusive. fetcher(a, b) returns the
    raw logs for one window or raises; a range complaint halves the window,
    other errors back off and retry. fetcher and sleep are injected for tests."""
    out = []
    start = from_block
    span = max(1, block_range)
    while start <= to_block:
        end = min(start + span - 1, to_block)
        try:
            out.extend(_fetch_window(fetcher, start, end, max_retries,
                                     base_delay, sleep))
        except RpcRangeError:
            if span <= min_range:
                raise
            span = max(min_range, span // 2)
            continue
        start = end + 1
    return out


def _fetch_window(fetcher, start, end, max_retries, base_delay, sleep):
    for attempt in range(max_retries):
        try:
            return fetcher(start, end)
        except RpcRangeError:
            raise
        except Exception as exc:
            if is_range_error(str(exc)):
                raise RpcRangeError(str(exc)) from exc
            if attempt == max_retries - 1:
                raise
            sleep(base_delay * (2 ** attempt))
    return []


def _value(raw) -> int:
    if raw in (None, "", "0x"):
        return 0
    return int(raw, 16)


def parse_erc20_approval(log: dict) -> dict:
    topics = log["topics"]
    return {
        "kind": "erc20",
        "token": to_checksum_address(log["address"]),
        "owner": _topic_addr(topics[1]),
        "spender": _topic_addr(topics[2]),
        "value": _value(log.get("data")),
        "block": int(log["blockNumber"], 16),
        "tx": log.get("transactionHash", ""),
    }


def parse_approval_for_all(log: dict) -> dict:
    topics = log["topics"]
    approved = _value(log.get("data")) != 0
    return {
        "kind": "erc721",
        "token": to_checksum_address(log["address"]),
        "owner": _topic_addr(topics[1]),
        "spender": _topic_addr(topics[2]),
        "approved": approved,
        "value": 1 if approved else 0,
        "block": int(log["blockNumber"], 16),
        "tx": log.get("transactionHash", ""),
    }


def _topic_addr(topic: str) -> str:
    raw = topic.removeprefix("0x") if isinstance(topic, str) else topic.hex()
    return to_checksum_address("0x" + raw[-40:])
