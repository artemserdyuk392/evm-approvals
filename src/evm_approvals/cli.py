"""Command line entry point: evm-approvals scan 0xADDRESS --chain ethereum."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from eth_utils import is_address, to_checksum_address
from rich.console import Console

from .approvals import scan
from .cache import Cache
from .chains import CHAINS, get_chain
from .explorer import Explorer
from .output import render_revoke, render_table, to_json
from .rpc import Rpc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evm-approvals",
        description="Read-only audit of ERC-20 and ERC-721 approvals.")
    sub = parser.add_subparsers(dest="command", required=True)
    scan_p = sub.add_parser("scan", help="audit approvals for an address")
    scan_p.add_argument("address", help="the owner address to audit")
    scan_p.add_argument("--chain", default="ethereum", choices=sorted(CHAINS))
    scan_p.add_argument("--rpc", help="override the RPC URL")
    scan_p.add_argument("--block-range", type=int, default=10000,
                        help="initial getLogs window size (default 10000)")
    scan_p.add_argument("--from-block", type=int,
                        help="first block to scan (default: cache or 0)")
    scan_p.add_argument("--days", type=int, default=90,
                        help="age in days after which an approval counts as stale")
    scan_p.add_argument("--json", action="store_true", help="print JSON")
    scan_p.add_argument("--revoke-calldata", action="store_true",
                        help="print revoke calldata for each approval")
    scan_p.add_argument("--no-cache", action="store_true",
                        help="ignore and do not write the SQLite cache")
    scan_p.add_argument("--db", help="cache database path")
    scan_p.add_argument("--explorer-key",
                        help="block explorer API key for source verification")
    return parser


def main(argv=None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    if args.command == "scan":
        return _run_scan(args)
    return 1


def _run_scan(args) -> int:
    console = Console()
    err = Console(stderr=True)
    if not is_address(args.address):
        err.print(f"[red]not a valid address: {args.address}[/]")
        return 2

    owner = to_checksum_address(args.address)
    chain = get_chain(args.chain)
    rpc_url = args.rpc or os.environ.get(chain.rpc_env) or chain.default_rpc
    rpc = Rpc.connect(chain, rpc_url)

    cache = None
    if not args.no_cache:
        cache = Cache(args.db or _default_db())

    explorer = None
    key = args.explorer_key or os.environ.get(chain.explorer_key_env)
    if key:
        explorer = Explorer(chain.explorer_api, key, chain.chain_id)

    try:
        items = scan(rpc, owner, block_range=args.block_range,
                     from_block=args.from_block, stale_days=args.days,
                     cache=cache, explorer=explorer)
    except Exception as exc:
        err.print(f"[red]scan failed: {exc}[/]")
        return 1
    finally:
        if cache is not None:
            cache.close()

    if args.json:
        print(to_json(items, chain.name, chain.chain_id))
    elif args.revoke_calldata:
        render_revoke(items, chain.name, chain.chain_id)
    elif not items:
        console.print(f"No live approvals found for {owner} on {chain.name}.")
    else:
        render_table(items, chain.name, console=console)
    return 0


def _default_db() -> str:
    return str(Path.home() / ".cache" / "evm-approvals" / "cache.db")


if __name__ == "__main__":
    raise SystemExit(main())
