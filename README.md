# evm-approvals

![ci](https://github.com/artemserdyuk392/evm-approvals/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)

Read-only audit of the ERC-20 and ERC-721 approvals an EVM address has granted.

The most common way funds leave an EVM wallet is not a stolen key. It is a live
`approve` to a contract that later turned out to be malicious or compromised,
granted once and forgotten. An `approve(spender, 2**256-1)` in particular leaves
an unlimited allowance that stays active forever. This tool lists those live
approvals so you can decide what to revoke. It only reads the chain: it never
signs, never sends a transaction, and never asks for a private key.

## How it works

1. Read `Approval` and `ApprovalForAll` logs for the address via `eth_getLogs`.
2. Re-read the current on-chain value for every `(token, spender)` pair with
   `allowance` or `isApprovedForAll`, and drop anything that is now zero. Logs
   are history, not state: an approval that was later revoked shows up in the
   logs but is filtered out here.
3. Enrich each survivor with token symbol, decimals, and your balance.
4. Score it against the rules in `rules.py` and print the result.

## Install

From source, into a virtual environment:

```bash
git clone https://github.com/artemserdyuk392/evm-approvals
cd evm-approvals
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

```bash
evm-approvals scan 0xYourAddress --chain ethereum
```

Supported chains: `ethereum`, `arbitrum`, `optimism`, `base`, `polygon`, `bsc`.

Output modes:

```bash
evm-approvals scan 0xYourAddress --chain ethereum --json
evm-approvals scan 0xYourAddress --chain ethereum --revoke-calldata
```

Useful flags:

- `--rpc URL` use a specific RPC endpoint (otherwise `.env` or a public default).
- `--block-range N` initial `eth_getLogs` window; it shrinks on its own when a
  node rejects the range (default 10000).
- `--from-block N` first block to scan; on a repeat run the SQLite cache picks
  up where the last scan stopped.
- `--days N` age after which an unused approval is reported as stale (default 90).
- `--explorer-key KEY` enable the "unverified spender source" check.
- `--no-cache` do not read or write the cache.

### Configuration

Copy `.env.example` to `.env` and fill in what you need:

```bash
cp .env.example .env
```

- `ETHEREUM_RPC_URL` (and the equivalents per chain): your RPC endpoint. The
  public defaults work but rate limit hard on a first full scan; a private
  endpoint from any provider is strongly recommended.
- `ETHERSCAN_API_KEY`: optional, enables source verification of spenders.

Nothing in `.env` is a signing key. The tool has no use for one.

## Risk rules

Risk is a plain checklist, not a weighted score. Each approval reports every
rule it triggered and takes the worst severity among them.

- `unlimited_allowance` (high): allowance is `2**256-1` and never decays.
- `allowance_exceeds_balance` (high): allowance is more than 10x the balance.
- `approval_for_all` (high): operator approved for a whole NFT collection.
- `spender_is_eoa` (high): spender has no contract code, almost always phishing.
- `spender_unverified` (medium): spender source is not verified on the explorer.
- `stale_approval` (medium): older than `--days` and unused since.
- `nonzero_allowance_zero_balance` (low): latent approval, nothing to take today.

## Security

This tool is read-only by design.

- It never asks for a private key, seed phrase, or wallet connection.
- It never builds, signs, or sends a transaction.
- `--revoke-calldata` prints the calldata for `approve(spender, 0)` or
  `setApprovalForAll(operator, false)`, the target contract, and the chain id.
  You paste that into a wallet you control and submit it yourself. Read what you
  are signing before you sign it.

Because revocation happens in your own wallet, this tool cannot move or lose
your funds even if the RPC endpoint it talks to is hostile.

## Limitations

- Completeness depends on the RPC. Public endpoints often serve limited history
  or cap `eth_getLogs` hard, so a scan may miss very old approvals. A private or
  archive endpoint plus `--from-block` near your first activity is the fix.
- The `stale_approval` rule uses a proxy for "not used since it was granted": it
  treats an approval as unused when the current allowance still equals the
  amount last approved. This proxy can be wrong in both directions. It misses an
  approval that was spent and then re-approved back to the same amount, and it
  can flag one whose allowance changed for a reason other than spending. Treat
  the flag as a hint, not a verdict.
- No Permit2 approvals. Allowances granted to the Permit2 contract, and the
  per-app permits inside it, are not decoded.
- No EIP-2612 permits. Gasless `permit()` approvals leave no `Approval` log to
  read and are not detected.
- No ERC-1155 single-token approvals. Only collection-wide `ApprovalForAll` is
  covered, which is what ERC-1155 exposes anyway.
- The logic is covered by unit tests that mock every RPC call. The tool has not
  yet been run against a real node, and its output has not been cross-checked
  against an independent source such as a block explorer or a revoke website.
  The first run against a live address is the first real-world test.

## License

MIT. See [LICENSE](LICENSE).
