# Flash Arb Bot — personal tool

Owner-only scanner for DiYJane. Not a product. Not for OG Founders. Not going on the shop.

Borrow USDC for one transaction. Buy the cheap V2 pool. Sell the rich V2 pool. Repay Aave + 5 bps. Keep the leftover. No leftover → revert. You still pay gas.

Paper mode is the default.

## Run

```bash
cd flash-arb-bot
python3 -m bot --demo
python3 -m bot --once
python3 -m bot --interval 2 --quiet
```

Scans Uni / Pancake / Sushi / BaseSwap V2 for WETH-USDC and WETH-USDbC. Each pass appends `logs/opps.jsonl`.

No private key needed to scan. `EXECUTE=1` still will not broadcast a public mempool tx. Deploy `contracts/FlashArb.sol` on a Base fork before any live path.
