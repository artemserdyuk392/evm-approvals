import pytest

from evm_approvals.chains import CHAINS, MULTICALL3, get_chain


def test_multicall3_address_is_the_canonical_one():
    assert MULTICALL3 == "0xcA11bde05977b3631167028862bE2a173976CA11"


def test_known_chain_ids():
    assert get_chain("ethereum").chain_id == 1
    assert get_chain("arbitrum").chain_id == 42161
    assert get_chain("base").chain_id == 8453
    assert {"ethereum", "arbitrum", "optimism", "base", "polygon", "bsc"} <= set(CHAINS)


def test_get_chain_is_case_insensitive():
    assert get_chain("Ethereum").name == "ethereum"


def test_unknown_chain_raises():
    with pytest.raises(KeyError):
        get_chain("dogechain")
