# Flash Arb Bot — Base + Aave V3

Borrow USDC for one transaction. Buy cheap pool. Sell rich pool. Repay loan + 5 bps. Keep the spread. If the spread is gone, the tx reverts and you only burn gas.

This is the scanner + executor skeleton for PopUpEmpire. Paper mode is the default. It is not a money printer.

## Money truth (read this)

Base printed ~21M successful cyclic arbs and ~986M failed/probe txs in one research window. The edge is measured in milliseconds and private orderflow, not a public RPC loop.

What this repo *does* make:

1. A working optimizer you can run in 10 seconds (`--demo`).
2. A live Base V2 scanner against Uniswap / Pancake / Sushi factories.
3. A Solidity flash-loan receiver that atomically reverts on no-profit.
4. A product you can sell as a fork-ready template to OG Founders instead of pretending mainnet is easy money.

What it does **not** do:

- Guarantee profit
- Beat professional searchers on public mempool
- Hide your tx from builders
- Need your private key to scan

## Run it now

```bash
cd flash-arb-bot
python3 -m bot --demo
```

Live paper scan (no key, no spend):

```bash
python3 -m bot --once
```

Continuous paper scan:

```bash
BASE_RPC=https://base.publicnode.com python3 -m bot --interval 2
```

Live fire stays off until you set `EXECUTE=1`, deploy `contracts/FlashArb.sol`, and fork-test. The template will still refuse to broadcast a raw public tx — that path is how you donate gas to sandwich bots.

## How the money path works

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
  repay USDC + 0.05%   |   leftover USDC = profit
  if leftover < minProfit → revert
```

Off-chain the scanner:

1. Reads `getReserves()` on each venue.
2. Sizes the borrow with a ternary search (profit is unimodal on a two-pool arb).
3. Subtracts Aave 5 bps + pool fees + a gas quote.
4. Prints the plan. Does not send.

## Addresses (Base, chain 8453)

| Piece | Address |
|---|---|
| Aave V3 Pool | `0xA238Dd80C259a72e81d7e4664a9801593F98d1c5` |
| USDC | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` |
| WETH | `0x4200000000000000000000000000000000000006` |
| Uni V2 factory | `0x8909Dc15e40173Ff4699343b6eB8132c65e18eC6` |
| Uni V2 WETH/USDC | `0x88A43bbDF9D098eec7bCeda4e2494615dfD9bB9C` |

Edit `config/venues.json` to add pairs. Empty `pair` fields are resolved via `factory.getPair`.

## Deploy (after a fork test)

1. Foundry or Remix, compiler 0.8.24.
2. Constructor arg = Aave V3 Pool on Base.
3. Owner-only `execute(asset, amount, buyPair, sellPair, minProfit)`.
4. Keep a few USDC on the contract only if you want a premium buffer. The happy path funds repayment from the second swap.
5. Submit through a private builder if you ever go live. Public mempool = you are exit liquidity.

## Fastest income from this repo

Do not wait for a $40 arb that 40 searchers already saw.

Sell the working template:

- Offer name: Base Flash Arb Starter
- Buyer: OG Founders / builders who want the wiring, not a signal group
- Delivery: this repo + a 30-min fork-test walkthrough
- Attach to the existing Wix shop, do not start a new brand

Scanner running in paper is the proof. Checkout is the income.

## Risk

Smart contract unaudited. Flash-loan callbacks can be griefed if you leave `execute` public — it is `onlyOwner`. Wrong pair order loses the tx to revert. Token fee-on-transfer pairs will break the math. You can lose gas every block if you spam.

Not financial advice. Not a managed strategy.
