from eth_abi import encode as abi_encode

from evm_approvals.abi import encode_decimals, encode_symbol, selector
from evm_approvals.enrich import enrich_tokens

OWNER = "0x1111111111111111111111111111111111111111"
TOKEN = "0x6B175474E89094C44Da98b954EedeAC495271d0F"


class _FakeRpc:
    """Answers eth_call by selector; reports no Multicall3 so enrich falls back
    to single calls. No network."""

    def __init__(self, table):
        self.table = table

    def get_code(self, address):
        return b""

    def call(self, to, data):
        return self.table.get(bytes(data[:4]), b"")


def test_enrich_reads_symbol_decimals_balance_with_bytes32_fallback():
    table = {
        encode_symbol(): b"DAI" + b"\x00" * 29,           # bytes32 symbol
        encode_decimals(): abi_encode(["uint256"], [18]),
        selector("balanceOf(address)"): abi_encode(["uint256"], [12345]),
    }
    result = enrich_tokens(_FakeRpc(table), OWNER, [TOKEN])
    assert result[TOKEN] == {"symbol": "DAI", "decimals": 18, "balance": 12345}


def test_enrich_handles_missing_metadata():
    # A token that reverts on every call yields empty returndata, so each field
    # falls back to its unknown value rather than raising.
    result = enrich_tokens(_FakeRpc({}), OWNER, [TOKEN])
    assert result[TOKEN] == {"symbol": "", "decimals": None, "balance": None}
