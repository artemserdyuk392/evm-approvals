import json

from evm_approvals.abi import MAX_UINT256
from evm_approvals.output import format_amount, revoke_calldata_for, sort_items, to_json
from evm_approvals.rules import Finding

TOKEN = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
SPENDER = "0x1111111111111111111111111111111111111111"


def _item(severity, kind="erc20", **kw):
    item = {
        "kind": kind, "token": TOKEN, "spender": SPENDER, "symbol": "DAI",
        "decimals": 18, "allowance": 1000, "approved": kind == "erc721",
        "balance": 0, "last_approve_time": 1_700_000_000,
        "severity": severity, "findings": [], "chain": "ethereum", "chain_id": 1,
    }
    item.update(kw)
    return item


def test_revoke_calldata_for_erc20():
    expected = ("0x095ea7b3"
                "0000000000000000000000001111111111111111111111111111111111111111"
                "0000000000000000000000000000000000000000000000000000000000000000")
    assert revoke_calldata_for(_item("high")) == expected


def test_revoke_calldata_for_erc721():
    calldata = revoke_calldata_for(_item("high", kind="erc721"))
    assert calldata.startswith("0xa22cb465")


def test_format_amount():
    assert format_amount(MAX_UINT256, 18) == "unlimited"
    assert format_amount(1_500_000_000_000_000_000, 18) == "1.5"
    assert format_amount(1000, None) == "1000"
    assert format_amount(None, 18) == "?"


def test_format_amount_never_shows_dust_as_zero():
    # 6 wei of WETH left to a spender after a partial spend, seen on mainnet.
    assert format_amount(6, 18) == "<0.0001"
    assert format_amount(0, 18) == "0"


def test_sort_items_orders_by_severity_then_recency():
    items = [_item("low"), _item("high"), _item("medium")]
    ordered = [it["severity"] for it in sort_items(items)]
    assert ordered == ["high", "medium", "low"]


def test_to_json_shape_includes_revoke_and_rules():
    item = _item("high", allowance=MAX_UINT256,
                 findings=[Finding("unlimited_allowance", "high", "reason")])
    payload = json.loads(to_json([item], "ethereum", 1))
    assert len(payload) == 1
    row = payload[0]
    assert row["chainId"] == 1
    assert row["allowance"] == "unlimited"
    assert row["severity"] == "high"
    assert row["rules"][0]["rule"] == "unlimited_allowance"
    assert row["revoke"]["to"] == TOKEN
    assert row["revoke"]["calldata"].startswith("0x095ea7b3")
