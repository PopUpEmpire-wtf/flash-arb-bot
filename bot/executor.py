"""Build and (optionally) send the flash-loan transaction.

Default is DRY_RUN. Live send requires EXECUTE=1 plus PRIVATE_KEY and
FLASH_ARB_CONTRACT. Failed arbs revert on-chain; you still pay gas.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass

from .scanner import Opportunity


@dataclass
class ExecutionPlan:
    mode: str
    profitable: bool
    amount_in: int
    expected_out: int
    net_profit: int
    buy_pair: str
    sell_pair: str
    note: str


def plan_from_opp(opp: Opportunity | None, gas_cost_quote: int) -> ExecutionPlan:
    if opp is None:
        return ExecutionPlan(
            mode="idle",
            profitable=False,
            amount_in=0,
            expected_out=0,
            net_profit=0,
            buy_pair="",
            sell_pair="",
            note="no spread after fees",
        )
    net_after_gas = opp.net_profit - gas_cost_quote
    return ExecutionPlan(
        mode="dry-run",
        profitable=net_after_gas > 0,
        amount_in=opp.amount_in,
        expected_out=opp.amount_out,
        net_profit=net_after_gas,
        buy_pair=opp.buy_pair,
        sell_pair=opp.sell_pair,
        note="paper trade — set EXECUTE=1 only after contract is deployed and tested on a fork",
    )


def maybe_send(plan: ExecutionPlan) -> ExecutionPlan:
    execute = os.getenv("EXECUTE", "0") == "1"
    if not execute:
        return plan
    contract = os.getenv("FLASH_ARB_CONTRACT", "")
    key = os.getenv("PRIVATE_KEY", "")
    if not contract or not key:
        plan.note = "EXECUTE=1 but FLASH_ARB_CONTRACT or PRIVATE_KEY missing — still paper"
        return plan
    plan.mode = "live-blocked"
    plan.note = (
        "live path is wired in contracts/FlashArb.sol. "
        "This runner will not broadcast from the template — "
        "deploy, fork-test, then hook a signer. Sending from a public "
        "mempool on Base gets you sandwiched."
    )
    return plan


def as_json(plan: ExecutionPlan) -> str:
    return json.dumps(asdict(plan), indent=2)
