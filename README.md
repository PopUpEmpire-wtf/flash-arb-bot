# Flash Arb Bot — personal tool

Owner-only scanner for DiYJane. Not a product. Not for OG Founders. Not going on the shop.

Borrow USDC for one transaction. Buy the cheap V2 pool. Sell the rich V2 pair. Repay Aave + 5 bps. Keep the leftover. No leftover → revert. You still pay gas.

Paper mode is the default.

## Run

```bash
cd flash-arb-bot
python3 -m bot --demo
python3 -m bot --once
BASE_RPC=https://base.publicnode.com python3 -m bot --interval 2
```

No private key needed to scan. `EXECUTE=1` still will not broadcast a public mempool tx. Deploy `contracts/FlashArb.sol` on a Base fork before any live path.

## Flow

```
Aave V3 flashLoanSimple(USDC)
        |
        v
  swap USDC → WETH on cheaper V2 pair
        |
        v
  swap WETH → USDC on richer V2 pair
        |
        v
  repay USDC + 0.05%   |   leftover = profit
  if leftover < minProfit → revert
```

Scanner reads `getReserves()`, sizes the borrow with a ternary search, subtracts flash fee + pool fees + a gas quote, prints the plan.

## Base addresses

| Piece | Address |
|---|---|
| Aave V3 Pool | `0xA238Dd80C259a72e81d7e4664a9801593F98d1c5` |
| USDC | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` |
| WETH | `0x4200000000000000000000000000000000000006` |
| Uni V2 factory | `0x8909Dc15e40173Ff4699343b6eB8132c65e18eC6` |
| Uni V2 WETH/USDC | `0x88A43bbDF9D098eec7bCeda4e2494615dfD9bB9C` |

Edit `config/venues.json` to add pairs.

## Deploy (fork first)

1. Compiler 0.8.24. Constructor arg = Aave V3 Pool.
2. Owner-only `execute(asset, amount, buyPair, sellPair, minProfit)`.
3. Live submits go through a private builder. Public mempool = sandwich bait.

## Risk

Unaudited. Wrong pair order reverts. Fee-on-transfer tokens break the math. Spamming costs gas every block. Not a managed strategy.
