"""Per-chain constants: chain id, a default public RPC, the explorer API, and
the env var checked for an RPC override. One dict, easy to extend."""

from __future__ import annotations

from dataclasses import dataclass

# Multicall3 is deployed at the same address on every chain listed here.
MULTICALL3 = "0xcA11bde05977b3631167028862bE2a173976CA11"

# Etherscan v2 serves every chain below through one endpoint and one key,
# selected by the chainid query parameter.
_ETHERSCAN_V2 = "https://api.etherscan.io/v2/api"


@dataclass(frozen=True)
class Chain:
    name: str
    chain_id: int
    default_rpc: str
    rpc_env: str
    explorer_api: str
    explorer_key_env: str


# A default must answer eth_getLogs filtered by topic alone, without a contract
# address; several popular keyless endpoints refuse exactly that query.
CHAINS = {
    "ethereum": Chain("ethereum", 1, "https://gateway.tenderly.co/public/mainnet",
                      "ETHEREUM_RPC_URL", _ETHERSCAN_V2, "ETHERSCAN_API_KEY"),
    "arbitrum": Chain("arbitrum", 42161, "https://arb1.arbitrum.io/rpc",
                      "ARBITRUM_RPC_URL", _ETHERSCAN_V2, "ETHERSCAN_API_KEY"),
    "optimism": Chain("optimism", 10, "https://mainnet.optimism.io",
                      "OPTIMISM_RPC_URL", _ETHERSCAN_V2, "ETHERSCAN_API_KEY"),
    "base": Chain("base", 8453, "https://mainnet.base.org",
                  "BASE_RPC_URL", _ETHERSCAN_V2, "ETHERSCAN_API_KEY"),
    "polygon": Chain("polygon", 137, "https://gateway.tenderly.co/public/polygon",
                     "POLYGON_RPC_URL", _ETHERSCAN_V2, "ETHERSCAN_API_KEY"),
    "bsc": Chain("bsc", 56, "https://bsc-dataseed.binance.org",
                 "BSC_RPC_URL", _ETHERSCAN_V2, "ETHERSCAN_API_KEY"),
}


def get_chain(name: str) -> Chain:
    key = name.lower()
    if key not in CHAINS:
        known = ", ".join(sorted(CHAINS))
        raise KeyError(f"unknown chain '{name}'; known chains: {known}")
    return CHAINS[key]
