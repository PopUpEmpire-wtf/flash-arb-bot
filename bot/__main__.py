#!/usr/bin/env python3
"""Owner flash-loan arb scanner. Paper by default.

  python -m bot --demo
  python -m bot --once
  python -m bot --interval 2
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .executor import maybe_send, plan_from_opp
from .rpc import Rpc, RpcError
from .scanner import Opportunity, Pool, find_opps, load_pools

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "config" / "venues.json").read_text())
LOG_PATH = ROOT / "logs" / "opps.jsonl"
TOKENS = {k: v.lower() for k, v in CFG["tokens"].items()}


def fmt_units(amount: int, decimals: int) -> str:
    if decimals <= 0:
        return str(amount)
    scale = 10 ** decimals
    whole, frac = divmod(amount, scale)
    return f"{whole}.{str(frac).zfill(decimals)[:6]}"


def demo_scan() -> list[Opportunity]:
    usdc = TOKENS["usdc"]
    weth = TOKENS["weth"]
    cheap = Pool(
        venue="demo-cheap",
        factory="0x" + "0" * 40,
        pair="0x" + "1" * 40,
        token0=weth,
        token1=usdc,
        reserve0=100 * 10**18,
        reserve1=246_000 * 10**6,
        fee_bps=30,
    )
    rich = Pool(
        venue="demo-rich",
        factory="0x" + "0" * 40,
        pair="0x" + "2" * 40,
        token0=weth,
        token1=usdc,
        reserve0=100 * 10**18,
        reserve1=254_000 * 10**6,
        fee_bps=30,
    )
    return find_opps(
        [cheap, rich],
        token_in=usdc,
        token_out=weth,
        flash_fee_bps=CFG["flash_fee_bps"],
        max_in=50_000 * 10**6,
        min_profit=10**5,
    )


def live_scan(rpc: Rpc, quiet: bool) -> list[Opportunity]:
    block = rpc.block_number()
    all_opps: list[Opportunity] = []
    if not quiet:
        print(f"block={block}")
    for spec in CFG["pairs"]:
        token_in = TOKENS[spec["token_in"]]
        token_out = TOKENS[spec["token_out"]]
        pools = load_pools(rpc, CFG["venues"], token_out, token_in)
        if not quiet:
            print(f"  {spec['name']} venues={len(pools)}")
            for p in pools:
                r_out = p.reserve0 if p.token0 == token_out else p.reserve1
                r_in = p.reserve1 if p.token0 == token_out else p.reserve0
                print(
                    f"    {p.venue:14} {p.pair}  "
                    f"out={fmt_units(r_out, spec['out_decimals'])}  "
                    f"in={fmt_units(r_in, spec['in_decimals'])}"
                )
        if len(pools) < 2:
            continue
        all_opps.extend(
            find_opps(
                pools,
                token_in=token_in,
                token_out=token_out,
                flash_fee_bps=CFG["flash_fee_bps"],
                max_in=int(CFG["max_flash_usdc"]) * 10**6,
                min_profit=int(CFG["min_profit_usdc"]) * 10**6,
            )
        )
    all_opps.sort(key=lambda o: o.net_profit, reverse=True)
    return all_opps


def print_opps(opps: list[Opportunity]) -> None:
    if not opps:
        print("no edge after flash fee + pool fees")
        return
    for i, o in enumerate(opps[:8], 1):
        print(
            f"[{i}] {o.buy_venue} -> {o.sell_venue}  "
            f"borrow {fmt_units(o.amount_in, 6)}  "
            f"net {fmt_units(o.net_profit, 6)}  "
            f"spread {o.spread_bps:.1f} bps"
        )


def log_pass(opps: list[Opportunity], plan_mode: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "mode": plan_mode,
        "hits": len(opps),
        "best_net": opps[0].net_profit if opps else 0,
        "best": None
        if not opps
        else {
            "buy": opps[0].buy_venue,
            "sell": opps[0].sell_venue,
            "amount_in": opps[0].amount_in,
            "net": opps[0].net_profit,
            "buy_pair": opps[0].buy_pair,
            "sell_pair": opps[0].sell_pair,
        },
    }
    with LOG_PATH.open("a") as fh:
        fh.write(json.dumps(row) + "\n")


def gas_quote_usdc(rpc: Rpc | None) -> int:
    gas_units = 250_000
    if rpc is None:
        return 50_000
    try:
        wei = rpc.gas_price_wei()
    except RpcError:
        return 50_000
    eth = wei * gas_units / 10**18
    return int(eth * 2500 * 10**6)


def run_once(demo: bool, quiet: bool) -> int:
    rpc = None
    if demo:
        opps = demo_scan()
        print("mode=DEMO synthetic WETH/USDC gap")
    else:
        url = os.getenv("BASE_RPC", CFG["rpc"])
        rpc = Rpc(url)
        try:
            opps = live_scan(rpc, quiet=quiet)
        except RpcError as exc:
            print(f"rpc failed: {exc}", file=sys.stderr)
            return 2
    print_opps(opps)
    best = opps[0] if opps else None
    plan = plan_from_opp(best, gas_quote_usdc(rpc))
    plan = maybe_send(plan)
    if not quiet or plan.profitable:
        print(plan.note)
        print(
            f"plan mode={plan.mode} profitable={plan.profitable} "
            f"net_after_gas={fmt_units(plan.net_profit, 6)}"
        )
    log_pass(opps, plan.mode)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Owner flash-loan arb scanner")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()
    if args.demo or args.once:
        return run_once(demo=args.demo, quiet=args.quiet)
    while True:
        code = run_once(demo=False, quiet=args.quiet)
        if code == 2:
            return 2
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
