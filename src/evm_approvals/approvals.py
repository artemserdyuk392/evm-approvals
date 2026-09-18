"""End-to-end scan: read Approval logs for an owner, re-read current on-chain
values to drop the revoked ones, enrich, score, and return result rows. The
re-read is the point of the tool: logs are history, not current state."""

from __future__ import annotations

import time

from .abi import (
    APPROVAL_FOR_ALL_TOPIC,
    APPROVAL_TOPIC,
    address_to_topic,
    decode_bool,
    decode_uint,
    encode_allowance,
    encode_is_approved_for_all,
)
from .enrich import enrich_tokens
from .logs import fetch_logs, parse_approval_for_all, parse_erc20_approval
from .multicall import multicall
from .rules import Approval, evaluate


def scan(rpc, owner, *, block_range=10000, from_block=None, stale_days=90,
         cache=None, explorer=None):
    chain = rpc.chain
    latest = rpc.block_number()
    start = _resolve_start(chain, owner, from_block, cache)

    records = _collect_logs(rpc, owner, start, latest, block_range)

    if cache is not None:
        cache.upsert_seen(chain.chain_id, owner, records)
        cache.set_last_block(chain.chain_id, owner, latest)
        history = cache.get_seen(chain.chain_id, owner)
    else:
        history = records

    pairs = _latest_pairs(records, history)
    live = _read_current_values(rpc, owner, pairs)
    if not live:
        return []

    enriched = enrich_tokens(rpc, owner, [p["token"] for p in live])
    _attach_metadata(rpc, owner, live, enriched, explorer)
    return _score(live, chain, stale_days)


def _resolve_start(chain, owner, from_block, cache):
    if from_block is not None:
        return from_block
    if cache is not None:
        last = cache.get_last_block(chain.chain_id, owner)
        if last is not None:
            return last + 1
    return 0


def _collect_logs(rpc, owner, start, latest, block_range):
    if start > latest:
        return []
    owner_topic = address_to_topic(owner)
    erc20 = fetch_logs(
        lambda a, b: rpc.get_logs(a, b, [APPROVAL_TOPIC, owner_topic]),
        start, latest, block_range=block_range)
    nfts = fetch_logs(
        lambda a, b: rpc.get_logs(a, b, [APPROVAL_FOR_ALL_TOPIC, owner_topic]),
        start, latest, block_range=block_range)
    return [parse_erc20_approval(log) for log in erc20] + \
           [parse_approval_for_all(log) for log in nfts]


def _latest_pairs(records, history):
    # Merge freshly read logs with the cached history and keep, per
    # (token, spender, kind), the record from the highest block.
    pairs = {}
    for r in list(history) + list(records):
        key = (r["token"], r["spender"], r["kind"])
        block = int(r["block"])
        current = pairs.get(key)
        if current is None or block >= current["block"]:
            pairs[key] = {
                "token": r["token"], "spender": r["spender"], "kind": r["kind"],
                "block": block, "value": int(r["value"]), "tx": r.get("tx", ""),
            }
    return list(pairs.values())


def _read_current_values(rpc, owner, pairs):
    calls = []
    for p in pairs:
        if p["kind"] == "erc20":
            calls.append((p["token"], encode_allowance(owner, p["spender"])))
        else:
            calls.append((p["token"], encode_is_approved_for_all(owner, p["spender"])))
    results = multicall(rpc, calls)
    live = []
    for p, (ok, ret) in zip(pairs, results):
        if not ok:
            continue
        if p["kind"] == "erc20":
            allowance = decode_uint(ret)
            if allowance == 0:
                continue
            p["allowance"], p["approved"] = allowance, False
        else:
            if not decode_bool(ret):
                continue
            p["allowance"], p["approved"] = 0, True
        live.append(p)
    return live


def _attach_metadata(rpc, owner, live, enriched, explorer):
    spenders = {p["spender"] for p in live}
    is_contract = {s: len(rpc.get_code(s)) > 0 for s in spenders}
    verified = {}
    if explorer is not None:
        verified = {s: explorer.is_verified(s) for s in spenders}
    timestamps = {b: rpc.block_timestamp(b) for b in {p["block"] for p in live}}
    for p in live:
        meta = enriched.get(p["token"], {})
        p["symbol"] = meta.get("symbol", "")
        p["decimals"] = meta.get("decimals")
        p["balance"] = meta.get("balance")
        p["spender_is_contract"] = is_contract.get(p["spender"], True)
        p["spender_verified"] = verified.get(p["spender"])
        p["last_approve_time"] = timestamps.get(p["block"]) or None


def _score(live, chain, stale_days):
    now = int(time.time())
    ctx = {"now": now, "stale_days": stale_days}
    items = []
    for p in live:
        approval = Approval(
            kind=p["kind"], token=p["token"], spender=p["spender"],
            symbol=p.get("symbol", ""), decimals=p.get("decimals"),
            allowance=p.get("allowance", 0), approved=p.get("approved", False),
            balance=p.get("balance"),
            last_approve_time=p.get("last_approve_time"),
            last_logged_value=p.get("value"),
            spender_is_contract=p.get("spender_is_contract", True),
            spender_verified=p.get("spender_verified"),
        )
        findings, severity = evaluate(approval, ctx)
        item = dict(p)
        item["severity"] = severity
        item["findings"] = findings
        item["chain"] = chain.name
        item["chain_id"] = chain.chain_id
        items.append(item)
    return items
