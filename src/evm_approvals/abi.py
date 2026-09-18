"""ABI helpers: event topics, function selectors, and the calldata for the few
ERC-20 and ERC-721 methods this tool reads or revokes. Everything is derived
from the text signatures so a typo cannot silently break a log filter."""

from __future__ import annotations

from eth_abi import decode as abi_decode
from eth_abi import encode as abi_encode
from eth_utils import keccak, to_checksum_address

MAX_UINT256 = 2**256 - 1

APPROVAL_SIG = "Approval(address,address,uint256)"
APPROVAL_FOR_ALL_SIG = "ApprovalForAll(address,address,bool)"


def event_topic(signature: str) -> str:
    return "0x" + keccak(text=signature).hex()


def selector(signature: str) -> bytes:
    return keccak(text=signature)[:4]


APPROVAL_TOPIC = event_topic(APPROVAL_SIG)
APPROVAL_FOR_ALL_TOPIC = event_topic(APPROVAL_FOR_ALL_SIG)


def address_to_topic(address: str) -> str:
    """Left-pad a 20-byte address to the 32-byte value used as an indexed topic."""
    return "0x" + address.lower().removeprefix("0x").rjust(64, "0")


def topic_to_address(topic: str) -> str:
    raw = topic.removeprefix("0x") if isinstance(topic, str) else topic.hex()
    return to_checksum_address("0x" + raw[-40:])


def encode_allowance(owner: str, spender: str) -> bytes:
    return selector("allowance(address,address)") + abi_encode(
        ["address", "address"], [owner, spender])


def encode_is_approved_for_all(owner: str, operator: str) -> bytes:
    return selector("isApprovedForAll(address,address)") + abi_encode(
        ["address", "address"], [owner, operator])


def encode_balance_of(owner: str) -> bytes:
    return selector("balanceOf(address)") + abi_encode(["address"], [owner])


def encode_symbol() -> bytes:
    return selector("symbol()")


def encode_decimals() -> bytes:
    return selector("decimals()")


def revoke_erc20_calldata(spender: str) -> str:
    data = selector("approve(address,uint256)") + abi_encode(
        ["address", "uint256"], [spender, 0])
    return "0x" + data.hex()


def revoke_erc721_calldata(operator: str) -> str:
    data = selector("setApprovalForAll(address,bool)") + abi_encode(
        ["address", "bool"], [operator, False])
    return "0x" + data.hex()


def decode_uint(data: bytes) -> int:
    if not data:
        return 0
    return abi_decode(["uint256"], data[:32])[0]


def decode_bool(data: bytes) -> bool:
    if not data:
        return False
    return bool(abi_decode(["bool"], data[:32])[0])


def decode_string_or_bytes32(data: bytes) -> str:
    """symbol() returns a string in the standard, but early tokens (MKR and
    kin) return a fixed bytes32. Try the standard encoding first, then fall
    back to trimming a raw bytes32."""
    if not data:
        return ""
    try:
        return abi_decode(["string"], data)[0]
    except Exception:
        pass
    try:
        raw = abi_decode(["bytes32"], data)[0]
    except Exception:
        raw = data[:32]
    return raw.rstrip(b"\x00").decode("utf-8", "replace")
