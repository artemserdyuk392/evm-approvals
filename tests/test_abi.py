from eth_abi import encode as abi_encode

from evm_approvals.abi import (
    APPROVAL_FOR_ALL_TOPIC,
    APPROVAL_TOPIC,
    address_to_topic,
    decode_string_or_bytes32,
    revoke_erc20_calldata,
    revoke_erc721_calldata,
    selector,
    topic_to_address,
)

SPENDER = "0x1111111111111111111111111111111111111111"
OPERATOR = "0x2222222222222222222222222222222222222222"


def test_event_topics_match_known_hashes():
    assert APPROVAL_TOPIC == (
        "0x8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925")
    assert APPROVAL_FOR_ALL_TOPIC == (
        "0x17307eab39ab6107e8899845ad3d59bd9653f200f220920489ca2b5937696c31")


def test_known_selectors():
    assert selector("approve(address,uint256)").hex() == "095ea7b3"
    assert selector("setApprovalForAll(address,bool)").hex() == "a22cb465"
    assert selector("allowance(address,address)").hex() == "dd62ed3e"


def test_revoke_erc20_calldata_matches_precomputed_hex():
    expected = ("0x095ea7b3"
                "0000000000000000000000001111111111111111111111111111111111111111"
                "0000000000000000000000000000000000000000000000000000000000000000")
    assert revoke_erc20_calldata(SPENDER) == expected


def test_revoke_erc721_calldata_matches_precomputed_hex():
    expected = ("0xa22cb465"
                "0000000000000000000000002222222222222222222222222222222222222222"
                "0000000000000000000000000000000000000000000000000000000000000000")
    assert revoke_erc721_calldata(OPERATOR) == expected


def test_address_topic_round_trip():
    topic = address_to_topic(SPENDER)
    assert topic == "0x" + "0" * 24 + "1" * 40
    assert topic_to_address(topic).lower() == SPENDER


def test_symbol_decode_standard_string():
    data = abi_encode(["string"], ["USDC"])
    assert decode_string_or_bytes32(data) == "USDC"


def test_symbol_decode_bytes32_fallback():
    # MKR and other early tokens return a raw bytes32 instead of a string.
    data = b"MKR" + b"\x00" * 29
    assert decode_string_or_bytes32(data) == "MKR"


def test_symbol_decode_empty():
    assert decode_string_or_bytes32(b"") == ""
