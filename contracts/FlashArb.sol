// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title FlashArb
/// @notice Aave V3 flashLoanSimple receiver that buys on one UniV2-style pair
///         and sells on another in the same transaction. Reverts unless the
///         loan + premium is repaid and minProfit is met.
/// @dev Deploy on Base. Owner-only entry. Not audited. Fork-test before mainnet.

interface IERC20 {
    function balanceOf(address) external view returns (uint256);
    function approve(address, uint256) external returns (bool);
    function transfer(address, uint256) external returns (bool);
}

interface IAavePool {
    function flashLoanSimple(
        address receiverAddress,
        address asset,
        uint256 amount,
        bytes calldata params,
        uint16 referralCode
    ) external;
}

interface IUniswapV2Pair {
    function token0() external view returns (address);
    function token1() external view returns (address);
    function swap(uint256 amount0Out, uint256 amount1Out, address to, bytes calldata data) external;
}

contract FlashArb {
    address public immutable AAVE_POOL;
    address public owner;

    error NotOwner();
    error NotPool();
    error NotThis();
    error NoProfit();
    error ZeroAddr();

    event Arb(address indexed asset, uint256 borrowed, uint256 profit);
    event OwnerSet(address indexed owner);

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    constructor(address aavePool) {
        if (aavePool == address(0)) revert ZeroAddr();
        AAVE_POOL = aavePool;
        owner = msg.sender;
        emit OwnerSet(msg.sender);
    }

    function setOwner(address next) external onlyOwner {
        if (next == address(0)) revert ZeroAddr();
        owner = next;
        emit OwnerSet(next);
    }

    function execute(
        address asset,
        uint256 amount,
        address buyPair,
        address sellPair,
        uint256 minProfit
    ) external onlyOwner {
        bytes memory params = abi.encode(buyPair, sellPair, minProfit, msg.sender);
        IAavePool(AAVE_POOL).flashLoanSimple(address(this), asset, amount, params, 0);
    }

    function executeOperation(
        address asset,
        uint256 amount,
        uint256 premium,
        address initiator,
        bytes calldata params
    ) external returns (bool) {
        if (msg.sender != AAVE_POOL) revert NotPool();
        if (initiator != address(this)) revert NotThis();

        (address buyPair, address sellPair, uint256 minProfit, address beneficiary) =
            abi.decode(params, (address, address, uint256, address));

        address midToken = _other(buyPair, asset);
        uint256 mid = _swap(buyPair, asset, amount, address(this));
        uint256 got = _swap(sellPair, midToken, mid, address(this));

        uint256 owed = amount + premium;
        if (got < owed + minProfit) revert NoProfit();

        IERC20(asset).approve(AAVE_POOL, owed);
        uint256 profit = IERC20(asset).balanceOf(address(this)) - owed;
        if (profit > 0) {
            IERC20(asset).transfer(beneficiary, profit);
        }
        emit Arb(asset, amount, profit);
        return true;
    }

    function sweep(address token) external onlyOwner {
        uint256 bal = IERC20(token).balanceOf(address(this));
        if (bal > 0) IERC20(token).transfer(owner, bal);
    }

    function _other(address pair, address token) internal view returns (address) {
        address t0 = IUniswapV2Pair(pair).token0();
        address t1 = IUniswapV2Pair(pair).token1();
        return token == t0 ? t1 : t0;
    }

    function _swap(address pair, address tokenIn, uint256 amountIn, address to) internal returns (uint256 amountOut) {
        address t0 = IUniswapV2Pair(pair).token0();
        (uint112 r0, uint112 r1, ) = _reserves(pair);
        bool zeroIn = tokenIn == t0;
        (uint256 rin, uint256 rout) = zeroIn ? (uint256(r0), uint256(r1)) : (uint256(r1), uint256(r0));
        amountOut = (amountIn * 997 * rout) / (rin * 1000 + amountIn * 997);
        IERC20(tokenIn).transfer(pair, amountIn);
        if (zeroIn) {
            IUniswapV2Pair(pair).swap(0, amountOut, to, "");
        } else {
            IUniswapV2Pair(pair).swap(amountOut, 0, to, "");
        }
    }

    function _reserves(address pair) internal view returns (uint112, uint112, uint32) {
        (bool ok, bytes memory data) = pair.staticcall(abi.encodeWithSignature("getReserves()"));
        require(ok && data.length >= 96, "reserves");
        return abi.decode(data, (uint112, uint112, uint32));
    }
}
