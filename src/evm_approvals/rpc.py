"""Thin web3 wrapper: build a client per chain and expose the handful of raw
JSON-RPC calls the scanner needs. Using make_request keeps error text intact
for range detection and sidesteps POA block-formatting quirks."""

from __future__ import annotations

import requests
from web3 import Web3

from .chains import Chain


class RpcError(Exception):
    pass


class Rpc:
    def __init__(self, w3: Web3, chain: Chain):
        self.w3 = w3
        self.chain = chain

    @classmethod
    def connect(cls, chain: Chain, rpc_url: str, timeout: int = 30) -> "Rpc":
        provider = Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": timeout})
        return cls(Web3(provider), chain)

    def block_number(self) -> int:
        return self.w3.eth.block_number

    def get_logs(self, from_block: int, to_block: int, topics: list) -> list:
        params = {
            "fromBlock": hex(from_block),
            "toBlock": hex(to_block),
            "topics": topics,
        }
        try:
            resp = self.w3.provider.make_request("eth_getLogs", [params])
        except requests.HTTPError as exc:
            # Many nodes refuse a range with a 4xx/5xx and put the reason in the
            # JSON body (Base: 413 "limited to a 500 range", drpc: 400).
            # raise_for_status reduces that to "413 Client Error", which range
            # detection cannot read, so recover the body when there is one.
            resp = _json_error(exc.response)
            if resp is None:
                raise
        error = resp.get("error")
        if error:
            raise RpcError(_message(error))
        return resp.get("result") or []

    def call(self, to: str, data, block: str = "latest") -> bytes:
        payload = data if isinstance(data, str) else "0x" + data.hex()
        resp = self.w3.provider.make_request("eth_call", [{"to": to, "data": payload}, block])
        if resp.get("error"):
            return b""
        return _hexbytes(resp.get("result"))

    def get_code(self, address: str) -> bytes:
        resp = self.w3.provider.make_request("eth_getCode", [address, "latest"])
        return _hexbytes(resp.get("result"))

    def block_timestamp(self, block_number: int) -> int:
        resp = self.w3.provider.make_request(
            "eth_getBlockByNumber", [hex(block_number), False])
        result = resp.get("result")
        if not result:
            return 0
        return int(result["timestamp"], 16)


def _message(error) -> str:
    if isinstance(error, dict):
        return str(error.get("message", error))
    return str(error)


def _json_error(response):
    try:
        body = response.json()
    except Exception:
        return None
    if isinstance(body, dict) and body.get("error"):
        return body
    return None


def _hexbytes(result) -> bytes:
    if not result or result == "0x":
        return b""
    return bytes.fromhex(result[2:])
