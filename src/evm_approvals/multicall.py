"""Batch view calls through Multicall3 so re-reading allowances for a long
approval history is a few requests, not hundreds. Falls back to one call each
when Multicall3 is not deployed on the chain."""

from __future__ import annotations

from eth_abi import decode as abi_decode
from eth_abi import encode as abi_encode

from .abi import selector
from .chains import MULTICALL3

_AGGREGATE3 = selector("aggregate3((address,bool,bytes)[])")


def encode_aggregate3(calls) -> bytes:
    # allowFailure is always True so one odd token cannot sink the whole batch.
    tuples = [(to, True, data) for to, data in calls]
    return _AGGREGATE3 + abi_encode(["(address,bool,bytes)[]"], [tuples])


def decode_aggregate3(returndata: bytes):
    decoded = abi_decode(["(bool,bytes)[]"], returndata)[0]
    return [(bool(ok), ret) for ok, ret in decoded]


def multicall(rpc, calls, chunk_size=400):
    """Run (target, calldata) view calls; return a list of (success, returndata)
    aligned with calls."""
    if not calls:
        return []
    if not _has_multicall(rpc):
        return [_single(rpc, to, data) for to, data in calls]
    out = []
    for i in range(0, len(calls), chunk_size):
        chunk = calls[i:i + chunk_size]
        ret = rpc.call(MULTICALL3, encode_aggregate3(chunk))
        if not ret:
            out.extend(_single(rpc, to, data) for to, data in chunk)
            continue
        out.extend(decode_aggregate3(ret))
    return out


def _single(rpc, to, data):
    ret = rpc.call(to, data)
    return (bool(ret), ret)


def _has_multicall(rpc) -> bool:
    cached = getattr(rpc, "_has_multicall3", None)
    if cached is not None:
        return cached
    try:
        present = len(rpc.get_code(MULTICALL3)) > 0
    except Exception:
        present = False
    try:
        rpc._has_multicall3 = present
    except Exception:
        pass
    return present
