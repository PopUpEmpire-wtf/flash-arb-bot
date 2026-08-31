"""Uniswap V2-style constant-product math.

Fees are in basis points. Uniswap V2 = 30 bps (0.30%).
"""

from __future__ import annotations


BPS = 10_000


def get_amount_out(amount_in: int, reserve_in: int, reserve_out: int, fee_bps: int = 30) -> int:
    if amount_in <= 0 or reserve_in <= 0 or reserve_out <= 0:
        return 0
    amount_in_with_fee = amount_in * (BPS - fee_bps)
    numerator = amount_in_with_fee * reserve_out
    denominator = reserve_in * BPS + amount_in_with_fee
    return numerator // denominator


def price_token0_in_token1(r0: int, r1: int) -> float:
    if r0 <= 0:
        return 0.0
    return r1 / r0


def two_pool_arb(
    amount_in: int,
    buy_rin: int,
    buy_rout: int,
    sell_rin: int,
    sell_rout: int,
    buy_fee_bps: int = 30,
    sell_fee_bps: int = 30,
) -> tuple[int, int]:
    """Buy token_out on pool A, sell it on pool B, return (amount_out, gross_profit)."""
    mid = get_amount_out(amount_in, buy_rin, buy_rout, buy_fee_bps)
    out = get_amount_out(mid, sell_rin, sell_rout, sell_fee_bps)
    return out, out - amount_in


def best_amount(
    buy_rin: int,
    buy_rout: int,
    sell_rin: int,
    sell_rout: int,
    buy_fee_bps: int = 30,
    sell_fee_bps: int = 30,
    flash_fee_bps: int = 5,
    max_in: int | None = None,
    iters: int = 48,
) -> tuple[int, int, int]:
    """Ternary-search the borrow size that maximizes profit after flash-loan fee.

    Returns (amount_in, amount_out, net_profit) where net_profit subtracts
    flash_fee_bps on the borrowed amount.
    """
    cap = min(buy_rin // 3, sell_rout // 3)
    if max_in is not None:
        cap = min(cap, max_in)
    if cap <= 0:
        return 0, 0, 0

    lo, hi = 1, cap

    def net(x: int) -> tuple[int, int]:
        out, gross = two_pool_arb(
            x, buy_rin, buy_rout, sell_rin, sell_rout, buy_fee_bps, sell_fee_bps
        )
        fee = (x * flash_fee_bps + BPS - 1) // BPS
        return out, gross - fee

    best_x, best_out, best_net = 0, 0, 0
    for _ in range(iters):
        if hi - lo < 3:
            break
        m1 = lo + (hi - lo) // 3
        m2 = hi - (hi - lo) // 3
        _, n1 = net(m1)
        _, n2 = net(m2)
        if n1 < n2:
            lo = m1
        else:
            hi = m2

    for x in range(max(1, lo), hi + 1):
        out, n = net(x)
        if n > best_net:
            best_x, best_out, best_net = x, out, n
    return best_x, best_out, best_net
