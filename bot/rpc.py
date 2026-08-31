"""Minimal JSON-RPC helper. Stdlib only."""

from __future__ import annotations

import json
import urllib.error
import urllib.request


GET_RESERVES_SELECTOR = "0x0902f1ac"
GET_PAIR_SELECTOR = "0xe6a43905"
TOKEN0_SELECTOR = "0x0dfe1681"
TOKEN1_SELECTOR = "0xd21220a7"


class RpcError(RuntimeError):
    pass


class Rpc:
    def __init__(self, url: str, timeout: float = 12.0):
        self.url = url
        self.timeout = timeout

    def call(self, method: str, params: list) -> object:
        body = json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        ).encode()
        req = urllib.request.Request(
            self.url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "popupempire-flash-arb/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise RpcError(f"RPC HTTP {exc.code}: {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise RpcError(f"RPC unreachable: {exc}") from exc
        if "error" in payload and payload["error"]:
            raise RpcError(str(payload["error"]))
        return payload.get("result")

    def eth_call(self, to: str, data: str) -> str:
        result = self.call("eth_call", [{"to": to, "data": data}, "latest"])
        if not isinstance(result, str) or result in ("0x", "0x0", None):
            raise RpcError(f"empty eth_call to {to}")
        return result

    def gas_price_wei(self) -> int:
        raw = self.call("eth_gasPrice", [])
        return int(raw, 16)

    def block_number(self) -> int:
        raw = self.call("eth_blockNumber", [])
        return int(raw, 16)


def pad_addr(addr: str) -> str:
    return addr.lower().replace("0x", "").rjust(64, "0")


def decode_address(word: str) -> str:
    return "0x" + word[-40:]


def get_pair(rpc: Rpc, factory: str, token_a: str, token_b: str) -> str:
    data = GET_PAIR_SELECTOR + pad_addr(token_a) + pad_addr(token_b)
    raw = rpc.eth_call(factory, data)
    pair = decode_address(raw[-64:])
    if int(pair, 16) == 0:
        return ""
    return pair


def get_tokens(rpc: Rpc, pair: str) -> tuple[str, str]:
    t0 = decode_address(rpc.eth_call(pair, TOKEN0_SELECTOR)[-64:])
    t1 = decode_address(rpc.eth_call(pair, TOKEN1_SELECTOR)[-64:])
    return t0.lower(), t1.lower()


def get_reserves(rpc: Rpc, pair: str) -> tuple[int, int]:
    raw = rpc.eth_call(pair, GET_RESERVES_SELECTOR)
    hexdata = raw[2:]
    r0 = int(hexdata[0:64], 16)
    r1 = int(hexdata[64:128], 16)
    return r0, r1
