"""Token metadata (symbol, decimals) and owner balance, batched via multicall,
with the bytes32-symbol fallback that older tokens still need."""

from __future__ import annotations

from .abi import (
    decode_string_or_bytes32,
    decode_uint,
    encode_balance_of,
    encode_decimals,
    encode_symbol,
)
from .multicall import multicall


def enrich_tokens(rpc, owner: str, tokens) -> dict:
    """Return {token: {symbol, decimals, balance}} for the given token addresses."""
    tokens = list(dict.fromkeys(tokens))
    if not tokens:
        return {}
    calls = []
    for token in tokens:
        calls.append((token, encode_symbol()))
        calls.append((token, encode_decimals()))
        calls.append((token, encode_balance_of(owner)))
    results = multicall(rpc, calls)
    out = {}
    for idx, token in enumerate(tokens):
        ok_sym, sym = results[3 * idx]
        ok_dec, dec = results[3 * idx + 1]
        ok_bal, bal = results[3 * idx + 2]
        out[token] = {
            "symbol": decode_string_or_bytes32(sym) if ok_sym else "",
            "decimals": decode_uint(dec) if (ok_dec and dec) else None,
            "balance": decode_uint(bal) if ok_bal else None,
        }
    return out
