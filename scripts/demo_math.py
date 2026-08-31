#!/usr/bin/env python3
"""Print one sized flash-loan arb from a synthetic gap."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.amm import best_amount

buy_usdc, buy_weth = 246_000 * 10**6, 100 * 10**18
sell_weth, sell_usdc = 100 * 10**18, 249_000 * 10**6

amt, out, net = best_amount(
    buy_rin=buy_usdc,
    buy_rout=buy_weth,
    sell_rin=sell_weth,
    sell_rout=sell_usdc,
    buy_fee_bps=30,
    sell_fee_bps=30,
    flash_fee_bps=5,
    max_in=50_000 * 10**6,
)
print(f"borrow_usdc={amt/1e6:.2f}")
print(f"return_usdc={out/1e6:.2f}")
print(f"net_after_flash_fee_usdc={net/1e6:.2f}")
