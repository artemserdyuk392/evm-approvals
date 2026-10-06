"""Render results three ways: a risk-sorted rich table, JSON, or ready-to-paste
revoke calldata. Nothing here signs or sends; calldata is text for the user's
own wallet to submit."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table

from .abi import MAX_UINT256, revoke_erc20_calldata, revoke_erc721_calldata
from .rules import SEVERITY_ORDER

_SEVERITY_STYLE = {"high": "bold red", "medium": "yellow", "low": "green"}


def revoke_calldata_for(item) -> str:
    if item["kind"] == "erc20":
        return revoke_erc20_calldata(item["spender"])
    return revoke_erc721_calldata(item["spender"])


def sort_items(items):
    return sorted(
        items,
        key=lambda it: (SEVERITY_ORDER[it["severity"]],
                        it.get("last_approve_time") or 0),
        reverse=True)


def render_table(items, chain_name, console=None):
    console = console or Console()
    table = Table(title=f"Live approvals on {chain_name}")
    for column in ("Risk", "Token", "Type", "Spender", "Allowance",
                   "Balance", "Last approve", "Rules"):
        justify = "right" if column in ("Allowance", "Balance") else "left"
        table.add_column(column, justify=justify)
    for it in sort_items(items):
        sev = it["severity"]
        table.add_row(
            f"[{_SEVERITY_STYLE[sev]}]{sev}[/]",
            it.get("symbol") or _short(it["token"]),
            "ERC-20" if it["kind"] == "erc20" else "ERC-721/1155",
            _short(it["spender"]),
            _allowance_cell(it),
            _balance_cell(it),
            _date(it.get("last_approve_time")),
            ", ".join(f.rule for f in it["findings"]) or "-",
        )
    console.print(table)


def render_revoke(items, chain_name, chain_id, out=print):
    # Plain print, not rich: the calldata must stay on one unwrapped line so it
    # copies cleanly into a wallet or a pipe.
    for it in sort_items(items):
        label = it.get("symbol") or it["token"]
        out(f"# {label} [{it['severity']}] spender {it['spender']}")
        out(f"chain: {chain_name} (chainId {chain_id})")
        out(f"to:    {it['token']}")
        out(f"data:  {revoke_calldata_for(it)}")
        out("")


def to_json(items, chain_name, chain_id) -> str:
    out = []
    for it in sort_items(items):
        out.append({
            "chain": chain_name,
            "chainId": chain_id,
            "token": it["token"],
            "symbol": it.get("symbol", ""),
            "type": it["kind"],
            "spender": it["spender"],
            "allowance": _allowance_json(it),
            "decimals": it.get("decimals"),
            "balance": None if it.get("balance") is None else str(it["balance"]),
            "lastApprove": it.get("last_approve_time"),
            "severity": it["severity"],
            "rules": [{"rule": f.rule, "severity": f.severity, "reason": f.reason}
                      for f in it["findings"]],
            "revoke": {"to": it["token"], "chainId": chain_id,
                       "calldata": revoke_calldata_for(it)},
        })
    return json.dumps(out, indent=2)


def format_amount(value, decimals) -> str:
    if value is None:
        return "?"
    if value >= MAX_UINT256:
        return "unlimited"
    if not decimals:
        return str(value)
    whole = value / (10 ** decimals)
    text = f"{whole:,.4f}".rstrip("0").rstrip(".")
    # A dust allowance left after partial spending would otherwise print as
    # "0" and look like a revoked approval that should not be listed at all.
    if text == "0" and value > 0:
        return "<0.0001"
    return text


def _allowance_cell(it) -> str:
    if it["kind"] != "erc20":
        return "all tokens"
    return format_amount(it.get("allowance", 0), it.get("decimals"))


def _balance_cell(it) -> str:
    if it["kind"] != "erc20":
        return "-"
    return format_amount(it.get("balance"), it.get("decimals"))


def _allowance_json(it):
    if it["kind"] != "erc20":
        return "all"
    value = it.get("allowance", 0)
    return "unlimited" if value >= MAX_UINT256 else str(value)


def _date(ts) -> str:
    if not ts:
        return "unknown"
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def _short(address) -> str:
    return address[:6] + ".." + address[-4:] if len(address) > 12 else address
