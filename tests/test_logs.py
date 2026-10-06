import pytest

from evm_approvals.abi import APPROVAL_FOR_ALL_TOPIC, APPROVAL_TOPIC, address_to_topic
from evm_approvals.logs import (
    RpcRangeError,
    fetch_logs,
    is_range_error,
    parse_approval_for_all,
    parse_erc20_approval,
)

OWNER = "0x1111111111111111111111111111111111111111"
SPENDER = "0x2222222222222222222222222222222222222222"
TOKEN = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"


def _erc20_log(value_hex, block="0x10"):
    return {
        "address": TOKEN,
        "topics": [APPROVAL_TOPIC, address_to_topic(OWNER),
                   address_to_topic(SPENDER)],
        "data": value_hex,
        "blockNumber": block,
        "transactionHash": "0xabc",
    }


def test_parse_erc20_approval():
    log = _erc20_log(
        "0x00000000000000000000000000000000000000000000000000000000000003e8")
    parsed = parse_erc20_approval(log)
    assert parsed["kind"] == "erc20"
    assert parsed["token"] == TOKEN
    assert parsed["owner"].lower() == OWNER
    assert parsed["spender"].lower() == SPENDER
    assert parsed["value"] == 1000
    assert parsed["block"] == 16


def test_parse_approval_for_all():
    log = {
        "address": TOKEN,
        "topics": [APPROVAL_FOR_ALL_TOPIC, address_to_topic(OWNER),
                   address_to_topic(SPENDER)],
        "data": "0x0000000000000000000000000000000000000000000000000000000000000001",
        "blockNumber": "0x20",
        "transactionHash": "0xdef",
    }
    parsed = parse_approval_for_all(log)
    assert parsed["kind"] == "erc721"
    assert parsed["approved"] is True
    assert parsed["value"] == 1
    assert parsed["block"] == 32


def test_parse_approval_for_all_revoked_is_false():
    log = {
        "address": TOKEN,
        "topics": [APPROVAL_FOR_ALL_TOPIC, address_to_topic(OWNER),
                   address_to_topic(SPENDER)],
        "data": "0x0000000000000000000000000000000000000000000000000000000000000000",
        "blockNumber": "0x20",
        "transactionHash": "0xdef",
    }
    assert parse_approval_for_all(log)["approved"] is False


class _RangeLimitedNode:
    """Fake node that rejects any window wider than max_span, like a public RPC."""

    def __init__(self, max_span):
        self.max_span = max_span
        self.calls = []

    def __call__(self, start, end):
        self.calls.append((start, end))
        if end - start + 1 > self.max_span:
            raise Exception("block range is too wide, please narrow it")
        return [{"from": start, "to": end}]


def test_fetch_logs_narrows_window_on_range_error():
    node = _RangeLimitedNode(max_span=1000)
    logs = fetch_logs(node, 0, 5000, block_range=10000, sleep=lambda s: None)

    windows = sorted((row["from"], row["to"]) for row in logs)
    assert windows[0][0] == 0
    assert windows[-1][1] == 5000
    # every accepted window respects the node limit ...
    assert all(end - start + 1 <= 1000 for start, end in windows)
    # ... and the windows tile the range with no gaps or overlaps.
    for (_, prev_end), (next_start, _) in zip(windows, windows[1:]):
        assert next_start == prev_end + 1


def test_fetch_logs_names_the_window_when_it_cannot_narrow_further():
    # bsc-dataseed answers "limit exceeded" to any eth_getLogs, even one block.
    def node(start, end):
        raise Exception("limit exceeded")

    with pytest.raises(RpcRangeError, match="even for a 1-block window: limit exceeded"):
        fetch_logs(node, 0, 5000, block_range=1000, sleep=lambda s: None)


class _FlakyNode:
    def __init__(self, fail_times):
        self.fail_times = fail_times
        self.attempts = 0

    def __call__(self, start, end):
        self.attempts += 1
        if self.attempts <= self.fail_times:
            raise Exception("connection reset by peer")
        return [{"from": start, "to": end}]


def test_fetch_logs_retries_transient_errors():
    node = _FlakyNode(fail_times=2)
    logs = fetch_logs(node, 0, 10, block_range=100, sleep=lambda s: None)
    assert logs == [{"from": 0, "to": 10}]
    assert node.attempts == 3


def test_fetch_logs_reraises_non_range_error_after_retries():
    node = _FlakyNode(fail_times=99)
    with pytest.raises(Exception, match="connection reset"):
        fetch_logs(node, 0, 10, block_range=100, max_retries=3,
                   sleep=lambda s: None)


def test_is_range_error_recognises_provider_messages():
    messages = [
        "query returned more than 10000 results",
        "Log response size exceeded. You can make eth_getLogs requests with up to a 2K block range",
        "block range is too wide",
        "eth_getLogs is limited to a 10000 range",
        "please limit the query to at most 800 blocks",
        "the range of blocks is too large",
    ]
    assert all(is_range_error(m) for m in messages)


@pytest.mark.parametrize("message", [
    # Verbatim answers from public nodes to a too-wide eth_getLogs window.
    "eth_getLogs is limited to a 500 range",
    "query spans 100000 blocks (511978060 to 512078059), but only 30000 are allowed "
    "for this request; narrow the block range, or add an address filter",
    "ranges over 10000 blocks are not supported on free plan",
    "eth_getLogs is limited to 0 - 50 blocks range",
    "You can make eth_getLogs requests with up to a 10 block range.",
    "Block range too large: maximum allowed is 50 blocks on your current plan.",
    "log query range must not exceed 25 blocks",
])
def test_is_range_error_recognises_live_node_messages(message):
    assert is_range_error(message)


def test_is_range_error_ignores_unrelated_messages():
    assert not is_range_error("connection reset by peer")
    assert not is_range_error("insufficient funds for gas")


def test_is_range_error_treats_rate_limits_as_transient():
    # Real bodies seen from public nodes; the first one contains the
    # "limit exceeded" range marker.
    assert not is_range_error("rate limit exceeded")
    assert not is_range_error("Your request has been rate-limited due to unusually high traffic")
    assert not is_range_error("Too Many Requests, Please apply an OnFinality API key")


def test_fetch_logs_does_not_narrow_on_rate_limit():
    attempts = []

    def node(start, end):
        attempts.append((start, end))
        if len(attempts) == 1:
            raise Exception("rate limit exceeded")
        return [{"from": start, "to": end}]

    logs = fetch_logs(node, 0, 999, block_range=1000, sleep=lambda s: None)
    assert logs == [{"from": 0, "to": 999}]
    assert attempts == [(0, 999), (0, 999)]
