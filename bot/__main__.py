#!/usr/bin/env python3
"""PopUpEmpire flash-loan arb scanner.

  python -m bot --demo          # synthetic spread, proves the money math
  python -m bot                 # live Base scan, paper trade by default
  python -m bot --once          # single pass then exit
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from .executor import maybe_send, plan_from_opp
from .rpc import Rpc, RpcError
from .scanner import Opportunity, Pool, find_opps, load_pools

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "config" / "venues.json").read_text())


def fmt_units(amount: int, decimals: int) -> str:
    if decimals <= 0:
        return str(amount)
    scale = 10 ** decimals
    whole, frac = divmod(amount, scale)
    return f"{whole}.{str(frac).zfill(decimals)[:6]}"


def demo_scan() -> list[Opportunity]:
    """Inject a mid-price gap so the optimizer has something to chew."""
    usdc = CFG["usdc"].lower()
    weth = CFG["weth"].lower()
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


def live_scan(rpc: Rpc) -> list[Opportunity]:
    pools = load_pools(rpc, CFG["venues"], CFG["weth"], CFG["usdc"])
    if len(pools) < 2:
        print(f"need 2+ live V2 pools, got {len(pools)}", file=sys.stderr)
        for p in pools:
            print(f"  {p.venue} {p.pair} r0={p.reserve0} r1={p.reserve1}", file=sys.stderr)
        return []
    print(f"block={rpc.block_number()} pools={len(pools)}")
    for p in pools:
        print(
            f"  {p.venue:16} {p.pair}  "
            f"WETH={fmt_units(p.reserve0 if p.token0==CFG['weth'].lower() else p.reserve1, 18)}  "
            f"USDC={fmt_units(p.reserve1 if p.token0==CFG['weth'].lower() else p.reserve0, 6)}"
        )
    return find_opps(
        pools,
        token_in=CFG["usdc"],
        token_out=CFG["weth"],
        flash_fee_bps=CFG["flash_fee_bps"],
        max_in=int(CFG["max_flash_usdc"]) * 10**6,
        min_profit=int(CFG["min_profit_usdc"]) * 10**6,
    )


def print_opps(opps: list[Opportunity]) -> None:
    if not opps:
        print("no edge after 5 bps flash fee + pool fees")
        return
    for i, o in enumerate(opps[:5], 1):
        print(
            f"[{i}] buy {o.buy_venue} -> sell {o.sell_venue}  "
            f"borrow {fmt_units(o.amount_in, 6)} USDC  "
            f"net {fmt_units(o.net_profit, 6)} USDC  "
            f"spread {o.spread_bps:.1f} bps"
        )


def gas_quote_usdc(rpc: Rpc | None) -> int:
    """Rough USDC gas budget. Flash-loan two-hop ~250k gas on Base."""
    gas_units = 250_000
    if rpc is None:
        return 50_000
    try:
        wei = rpc.gas_price_wei()
    except RpcError:
        return 50_000
    eth = wei * gas_units / 10**18
    return int(eth * 2500 * 10**6)


def run_once(demo: bool) -> int:
    rpc = None
    if demo:
        opps = demo_scan()
        print("mode=DEMO synthetic WETH/USDC gap")
    else:
        url = os.getenv("BASE_RPC", CFG["rpc"])
        rpc = Rpc(url)
        try:
            opps = live_scan(rpc)
        except RpcError as exc:
            print(f"rpc failed: {exc}", file=sys.stderr)
            return 2
    print_opps(opps)
    best = opps[0] if opps else None
    plan = plan_from_opp(best, gas_quote_usdc(rpc))
    plan = maybe_send(plan)
    print(plan.note)
    print(
        f"plan mode={plan.mode} profitable={plan.profitable} "
        f"net_after_gas={fmt_units(plan.net_profit, 6)} USDC"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Flash-loan arb scanner")
    parser.add_argument("--demo", action="store_true", help="run synthetic profitable path")
    parser.add_argument("--once", action="store_true", help="single scan")
    parser.add_argument("--interval", type=float, default=2.0, help="seconds between live scans")
    args = parser.parse_args()
    if args.demo or args.once:
        return run_once(demo=args.demo)
    while True:
        code = run_once(demo=False)
        if code == 2:
            return 2
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
