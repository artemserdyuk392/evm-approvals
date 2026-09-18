from evm_approvals.cache import Cache

CHAIN_ID = 1
OWNER = "0x1111111111111111111111111111111111111111"
TOKEN = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
SPENDER = "0x2222222222222222222222222222222222222222"


def _record(block, value):
    return {"token": TOKEN, "spender": SPENDER, "kind": "erc20",
            "block": block, "value": value, "tx": "0xabc"}


def test_last_block_round_trip():
    cache = Cache(":memory:")
    assert cache.get_last_block(CHAIN_ID, OWNER) is None
    cache.set_last_block(CHAIN_ID, OWNER, 12345)
    assert cache.get_last_block(CHAIN_ID, OWNER) == 12345
    cache.set_last_block(CHAIN_ID, OWNER, 20000)
    assert cache.get_last_block(CHAIN_ID, OWNER) == 20000


def test_seen_upsert_keeps_latest_block():
    cache = Cache(":memory:")
    cache.upsert_seen(CHAIN_ID, OWNER, [_record(100, 500)])
    cache.upsert_seen(CHAIN_ID, OWNER, [_record(200, 999)])
    # an older log must not overwrite the newer value
    cache.upsert_seen(CHAIN_ID, OWNER, [_record(150, 111)])

    seen = cache.get_seen(CHAIN_ID, OWNER)
    assert len(seen) == 1
    assert seen[0]["block"] == 200
    assert seen[0]["value"] == "999"


def test_seen_is_scoped_by_owner():
    cache = Cache(":memory:")
    cache.upsert_seen(CHAIN_ID, OWNER, [_record(100, 500)])
    other = "0x9999999999999999999999999999999999999999"
    assert cache.get_seen(CHAIN_ID, other) == []
