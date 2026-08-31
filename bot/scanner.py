"""Discover two-pool V2 spreads and size a flash loan."""

from __future__ import annotations

from dataclasses import dataclass

from .amm import best_amount, price_token0_in_token1
from .rpc import Rpc, get_pair, get_reserves, get_tokens


@dataclass
class Pool:
    venue: str
    factory: str
    pair: str
    token0: str
    token1: str
    reserve0: int
    reserve1: int
    fee_bps: int

    def reserves_for_buy(self, token_in: str) -> tuple[int, int]:
        token_in = token_in.lower()
        if token_in == self.token0:
            return self.reserve0, self.reserve1
        if token_in == self.token1:
            return self.reserve1, self.reserve0
        raise ValueError("token not in pool")


@dataclass
class Opportunity:
    buy_venue: str
    sell_venue: str
    token_in: str
    token_out: str
    amount_in: int
    amount_out: int
    net_profit: int
    buy_pair: str
    sell_pair: str
    spread_bps: float


def load_pools(rpc: Rpc, venues: list[dict], token_a: str, token_b: str) -> list[Pool]:
    pools: list[Pool] = []
    for venue in venues:
        try:
            pair = (venue.get("pair") or "").strip()
            if not pair:
                pair = get_pair(rpc, venue["factory"], token_a, token_b)
            if not pair:
                continue
            t0, t1 = get_tokens(rpc, pair)
            r0, r1 = get_reserves(rpc, pair)
        except Exception:
            continue
        if r0 == 0 or r1 == 0:
            continue
        pools.append(
            Pool(
                venue=venue["name"],
                factory=venue["factory"],
                pair=pair.lower(),
                token0=t0,
                token1=t1,
                reserve0=r0,
                reserve1=r1,
                fee_bps=int(venue.get("fee_bps", 30)),
            )
        )
    return pools


def find_opps(
    pools: list[Pool],
    token_in: str,
    token_out: str,
    flash_fee_bps: int,
    max_in: int,
    min_profit: int,
) -> list[Opportunity]:
    token_in = token_in.lower()
    token_out = token_out.lower()
    found: list[Opportunity] = []
    for buy in pools:
        for sell in pools:
            if buy.pair == sell.pair:
                continue
            try:
                buy_rin, buy_rout = buy.reserves_for_buy(token_in)
                sell_rin, sell_rout = sell.reserves_for_buy(token_out)
            except ValueError:
                continue
            amount_in, amount_out, net = best_amount(
                buy_rin,
                buy_rout,
                sell_rin,
                sell_rout,
                buy.fee_bps,
                sell.fee_bps,
                flash_fee_bps,
                max_in,
            )
            if net < min_profit:
                continue
            p_buy = buy_rout / buy_rin if buy_rin else 0
            p_sell = sell_rin / sell_rout if sell_rout else 0
            spread = 0.0
            if p_buy and p_sell:
                spread = (p_sell - p_buy) / p_buy * 10_000
            found.append(
                Opportunity(
                    buy_venue=buy.venue,
                    sell_venue=sell.venue,
                    token_in=token_in,
                    token_out=token_out,
                    amount_in=amount_in,
                    amount_out=amount_out,
                    net_profit=net,
                    buy_pair=buy.pair,
                    sell_pair=sell.pair,
                    spread_bps=spread,
                )
            )
    found.sort(key=lambda o: o.net_profit, reverse=True)
    return found


def mid_price(pool: Pool, quote_token: str) -> float:
    quote_token = quote_token.lower()
    if pool.token0 == quote_token:
        return price_token0_in_token1(pool.reserve1, pool.reserve0)
    return price_token0_in_token1(pool.reserve0, pool.reserve1)
