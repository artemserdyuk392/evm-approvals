from eth_abi import encode as abi_encode

from evm_approvals.abi import encode_allowance
from evm_approvals.chains import MULTICALL3
from evm_approvals.multicall import decode_aggregate3, encode_aggregate3, multicall

OWNER = "0x1111111111111111111111111111111111111111"
SPENDER = "0x2222222222222222222222222222222222222222"
TOKEN = "0x6B175474E89094C44Da98b954EedeAC495271d0F"


def test_aggregate3_round_trip():
    calls = [(TOKEN, encode_allowance(OWNER, SPENDER))]
    encoded = encode_aggregate3(calls)
    assert encoded[:4].hex() == "82ad56cb"  # aggregate3 selector
    ret = abi_encode(["(bool,bytes)[]"], [[(True, b"\x11" * 32)]])
    assert decode_aggregate3(ret) == [(True, b"\x11" * 32)]


class _MulticallRpc:
    """Reports Multicall3 present and echoes one aggregate3 result per call."""

    def __init__(self, values):
        self.values = values
        self.batches = 0

    def get_code(self, address):
        return b"\x60\x00" if address == MULTICALL3 else b""

    def call(self, to, data):
        assert to == MULTICALL3
        self.batches += 1
        results = [(True, abi_encode(["uint256"], [v])) for v in self.values]
        return abi_encode(["(bool,bytes)[]"], [results])


def test_multicall_uses_aggregate3_when_available():
    rpc = _MulticallRpc(values=[7, 9])
    calls = [(TOKEN, encode_allowance(OWNER, SPENDER)),
             (TOKEN, encode_allowance(OWNER, SPENDER))]
    results = multicall(rpc, calls)
    assert rpc.batches == 1
    assert [r[0] for r in results] == [True, True]


class _NoMulticallRpc:
    def __init__(self):
        self.singles = 0

    def get_code(self, address):
        return b""

    def call(self, to, data):
        self.singles += 1
        return abi_encode(["uint256"], [1])


def test_multicall_falls_back_to_single_calls():
    rpc = _NoMulticallRpc()
    calls = [(TOKEN, b"\x00"), (TOKEN, b"\x01")]
    results = multicall(rpc, calls)
    assert rpc.singles == 2
    assert all(ok for ok, _ in results)
