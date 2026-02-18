// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "./interfaces/IIdentityRegistry.sol";

/**
 * @title AgentPaymentPool
 * @notice Manages x402 payment distribution for ERC-8004 agents.
 *         Agents earn micropayments based on reputation tiers for successful transfers.
 * @dev Implements circuit-breaker (Pausable), reentrancy guard, and per-agent caps.
 */
contract AgentPaymentPool is Ownable, Pausable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    // ─── Errors ────────────────────────────────────────────────────────────────

    error InvalidAgentId();
    error InvalidAmount();
    error InsufficientPoolBalance();
    error ExceedsWithdrawalCap();
    error PaymentRateNotSet();
    error ZeroAddress();
    error NotAuthorized();

    // ─── Events ────────────────────────────────────────────────────────────────

    /// @notice Emitted when the pool receives a deposit
    event PoolDeposited(address indexed depositor, address indexed token, uint256 amount);

    /// @notice Emitted when an agent receives a payment reward
    event PaymentRewarded(
        uint256 indexed agentId,
        address indexed paymentWallet,
        address indexed token,
        uint256 amount,
        uint256 cumulativeTotal
    );

    /// @notice Emitted when an agent's payment rate is updated
    event PaymentRateSet(uint256 indexed agentId, uint256 ratePerTransfer, uint8 reputationTier);

    /// @notice Emitted when an agent's payment wallet is registered
    event PaymentWalletRegistered(uint256 indexed agentId, address indexed wallet);

    /// @notice Emitted when the daily cap per agent is updated
    event DailyCapUpdated(uint256 newCap);

    // ─── Structs ───────────────────────────────────────────────────────────────

    struct AgentPaymentStats {
        uint256 totalEarned;
        uint256 lastPaymentTimestamp;
        uint256 dailyEarned;
        uint256 dailyResetTimestamp;
        uint256 paymentRate;       // rate in token units (18 decimals)
        uint8   reputationTier;    // 0=poor, 1=below_avg, 2=average, 3=good, 4=excellent
        address paymentWallet;
    }

    // ─── State ─────────────────────────────────────────────────────────────────

    IIdentityRegistry public immutable identityRegistry;

    /// @notice Payment token (e.g. USDm on Celo)
    address public paymentToken;

    /// @notice agentId => stats
    mapping(uint256 => AgentPaymentStats) private _stats;

    /// @notice Maximum daily earnings per agent (in token units)
    uint256 public dailyCapPerAgent;

    /// @notice Base payment rate per successful transfer (in token units, 18 decimals)
    uint256 public basePaymentRate;

    /// @notice Reputation tier multipliers (basis points, 10000 = 1x)
    /// Index: 0=poor(6000), 1=below_avg(8000), 2=average(10000), 3=good(12000), 4=excellent(15000)
    uint256[5] public tierMultipliers;

    // ─── Constructor ───────────────────────────────────────────────────────────

    constructor(
        address _identityRegistry,
        address _paymentToken,
        uint256 _basePaymentRate,
        uint256 _dailyCapPerAgent
    ) Ownable(msg.sender) {
        if (_identityRegistry == address(0)) revert ZeroAddress();
        if (_paymentToken == address(0)) revert ZeroAddress();
        if (_basePaymentRate == 0) revert InvalidAmount();

        identityRegistry = IIdentityRegistry(_identityRegistry);
        paymentToken = _paymentToken;
        basePaymentRate = _basePaymentRate;
        dailyCapPerAgent = _dailyCapPerAgent;

        // Default tier multipliers (basis points)
        tierMultipliers[0] = 6000;   // poor: 0.6x
        tierMultipliers[1] = 8000;   // below_average: 0.8x
        tierMultipliers[2] = 10000;  // average: 1.0x
        tierMultipliers[3] = 12000;  // good: 1.2x
        tierMultipliers[4] = 15000;  // excellent: 1.5x
    }

    // ─── External: deposit ─────────────────────────────────────────────────────

    /**
     * @notice Fund the payment pool with tokens
     * @param token Token address to deposit
     * @param amount Amount to deposit
     */
    function deposit(address token, uint256 amount) external nonReentrant whenNotPaused {
        if (amount == 0) revert InvalidAmount();
        IERC20(token).safeTransferFrom(msg.sender, address(this), amount);
        emit PoolDeposited(msg.sender, token, amount);
    }

    // ─── External: registerPaymentWallet ──────────────────────────────────────

    /**
     * @notice Register a payment wallet for an agent
     * @param agentId The agent ID
     * @param wallet The payment wallet address
     */
    function registerPaymentWallet(uint256 agentId, address wallet) external {
        if (!identityRegistry.exists(agentId)) revert InvalidAgentId();
        if (wallet == address(0)) revert ZeroAddress();

        // Only agent owner can register payment wallet
        address agentOwner = identityRegistry.ownerOf(agentId);
        if (msg.sender != agentOwner) revert NotAuthorized();

        _stats[agentId].paymentWallet = wallet;
        emit PaymentWalletRegistered(agentId, wallet);
    }

    // ─── External: setPaymentRate ──────────────────────────────────────────────

    /**
     * @notice Set payment rate for an agent based on reputation tier
     * @param agentId The agent ID
     * @param reputationTier Tier index 0-4
     */
    function setPaymentRate(uint256 agentId, uint8 reputationTier) external onlyOwner {
        if (!identityRegistry.exists(agentId)) revert InvalidAgentId();
        if (reputationTier > 4) revert InvalidAmount();

        uint256 rate = (basePaymentRate * tierMultipliers[reputationTier]) / 10000;
        _stats[agentId].paymentRate = rate;
        _stats[agentId].reputationTier = reputationTier;

        emit PaymentRateSet(agentId, rate, reputationTier);
    }

    // ─── External: withdrawPayment ─────────────────────────────────────────────

    /**
     * @notice Distribute payment reward to an agent after successful transfer
     * @param agentId The agent ID
     * @param transferAmount The transfer amount (used for proportional calculation)
     * @dev Only callable by owner (the CeloFlow backend/TEE)
     */
    function withdrawPayment(
        uint256 agentId,
        uint256 transferAmount
    ) external onlyOwner nonReentrant whenNotPaused returns (uint256 rewardAmount) {
        if (!identityRegistry.exists(agentId)) revert InvalidAgentId();

        AgentPaymentStats storage stats = _stats[agentId];

        if (stats.paymentWallet == address(0)) revert PaymentRateNotSet();
        if (stats.paymentRate == 0) revert PaymentRateNotSet();

        // Calculate reward: base_rate * reputation_modifier * transfer_amount_factor
        // transfer_amount_factor = min(transferAmount / 1e18, 100) to cap proportional scaling
        uint256 amountFactor = transferAmount > 100e18 ? 100e18 : transferAmount;
        rewardAmount = (stats.paymentRate * amountFactor) / 1e18;

        if (rewardAmount == 0) revert InvalidAmount();

        // Reset daily counter if 24h has passed
        if (block.timestamp >= stats.dailyResetTimestamp + 1 days) {
            stats.dailyEarned = 0;
            stats.dailyResetTimestamp = block.timestamp;
        }

        // Enforce daily cap
        uint256 remaining = dailyCapPerAgent > stats.dailyEarned
            ? dailyCapPerAgent - stats.dailyEarned
            : 0;

        if (remaining == 0) revert ExceedsWithdrawalCap();
        if (rewardAmount > remaining) {
            rewardAmount = remaining;
        }

        // Check pool balance
        uint256 currentBalance = IERC20(paymentToken).balanceOf(address(this));
        if (currentBalance < rewardAmount) revert InsufficientPoolBalance();

        // Update stats
        stats.totalEarned += rewardAmount;
        stats.dailyEarned += rewardAmount;
        stats.lastPaymentTimestamp = block.timestamp;

        // Transfer reward
        IERC20(paymentToken).safeTransfer(stats.paymentWallet, rewardAmount);

        emit PaymentRewarded(
            agentId,
            stats.paymentWallet,
            paymentToken,
            rewardAmount,
            stats.totalEarned
        );
    }

    // ─── External: getPaymentStats ─────────────────────────────────────────────

    /**
     * @notice Get payment statistics for an agent
     * @param agentId The agent ID
     */
    function getPaymentStats(uint256 agentId) external view returns (
        uint256 totalEarned,
        uint256 lastPaymentTimestamp,
        uint256 dailyEarned,
        uint256 paymentRate,
        uint8   reputationTier,
        address paymentWallet
    ) {
        AgentPaymentStats storage stats = _stats[agentId];
        return (
            stats.totalEarned,
            stats.lastPaymentTimestamp,
            stats.dailyEarned,
            stats.paymentRate,
            stats.reputationTier,
            stats.paymentWallet
        );
    }

    // ─── External: updateBaseRate ──────────────────────────────────────────────

    /**
     * @notice Update the base payment rate (admin only)
     * @param newRate New base rate in token units (18 decimals)
     */
    function updateBaseRate(uint256 newRate) external onlyOwner {
        if (newRate == 0) revert InvalidAmount();
        basePaymentRate = newRate;
    }

    /**
     * @notice Update daily cap per agent
     * @param newCap New daily cap in token units
     */
    function updateDailyCap(uint256 newCap) external onlyOwner {
        dailyCapPerAgent = newCap;
        emit DailyCapUpdated(newCap);
    }

    /**
     * @notice Update tier multipliers
     * @param multipliers Array of 5 multipliers in basis points
     */
    function updateTierMultipliers(uint256[5] calldata multipliers) external onlyOwner {
        for (uint256 i = 0; i < 5; i++) {
            tierMultipliers[i] = multipliers[i];
        }
    }

    // ─── Emergency controls ────────────────────────────────────────────────────

    /**
     * @notice Pause all payment operations (circuit breaker)
     */
    function pause() external onlyOwner {
        _pause();
    }

    /**
     * @notice Resume payment operations
     */
    function unpause() external onlyOwner {
        _unpause();
    }

    /**
     * @notice Emergency withdrawal of pool funds (owner only)
     * @param token Token to withdraw
     * @param to Destination address
     * @param amount Amount to withdraw
     */
    function emergencyWithdraw(
        address token,
        address to,
        uint256 amount
    ) external onlyOwner {
        if (to == address(0)) revert ZeroAddress();
        IERC20(token).safeTransfer(to, amount);
    }

    /**
     * @notice Get pool balance for a token
     * @param token Token address
     */
    function poolBalance(address token) external view returns (uint256) {
        return IERC20(token).balanceOf(address(this));
    }
}
