// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/AgentPaymentPool.sol";
import "../src/IdentityRegistry.sol";

/**
 * @title AgentPaymentPoolTest
 * @notice Foundry tests for AgentPaymentPool — x402 reputation-based reward distribution
 */
contract AgentPaymentPoolTest is Test {
    // ─── Contracts ─────────────────────────────────────────────────────────────
    AgentPaymentPool public pool;
    IdentityRegistry public registry;
    MockERC20 public token;

    // ─── Actors ────────────────────────────────────────────────────────────────
    address public owner = address(this);
    address public agent0Owner = makeAddr("agent0Owner");
    address public agent1Owner = makeAddr("agent1Owner");
    address public paymentWallet0 = makeAddr("paymentWallet0");
    address public paymentWallet1 = makeAddr("paymentWallet1");
    address public attacker = makeAddr("attacker");

    // ─── Constants ─────────────────────────────────────────────────────────────
    uint256 constant BASE_RATE = 0.005e18;  // 0.5% in 18 decimals
    uint256 constant DAILY_CAP = 100e18;    // 100 USDm daily cap
    uint256 constant POOL_FUND = 1000e18;   // 1000 USDm pool funding

    // ─── Setup ─────────────────────────────────────────────────────────────────

    function setUp() public {
        // Deploy mock token
        token = new MockERC20("USDm", "USDm", 18);

        // Deploy identity registry
        registry = new IdentityRegistry();

        // Deploy payment pool
        pool = new AgentPaymentPool(
            address(registry),
            address(token),
            BASE_RATE,
            DAILY_CAP
        );

        // Fund pool
        token.mint(owner, POOL_FUND);
        token.approve(address(pool), POOL_FUND);
        pool.deposit(address(token), POOL_FUND);

        // Register agents
        vm.prank(agent0Owner);
        registry.register("ipfs://agent0");

        vm.prank(agent1Owner);
        registry.register("ipfs://agent1");

        // Register payment wallets
        vm.prank(agent0Owner);
        pool.registerPaymentWallet(0, paymentWallet0);

        vm.prank(agent1Owner);
        pool.registerPaymentWallet(1, paymentWallet1);

        // Set payment rates (tier 3 = good, 1.2x)
        pool.setPaymentRate(0, 3);
        pool.setPaymentRate(1, 2);
    }

    // ─── Constructor ───────────────────────────────────────────────────────────

    function test_constructor_sets_state() public view {
        assertEq(address(pool.identityRegistry()), address(registry));
        assertEq(pool.paymentToken(), address(token));
        assertEq(pool.basePaymentRate(), BASE_RATE);
        assertEq(pool.dailyCapPerAgent(), DAILY_CAP);
    }

    function test_constructor_reverts_zero_registry() public {
        vm.expectRevert(AgentPaymentPool.ZeroAddress.selector);
        new AgentPaymentPool(address(0), address(token), BASE_RATE, DAILY_CAP);
    }

    function test_constructor_reverts_zero_token() public {
        vm.expectRevert(AgentPaymentPool.ZeroAddress.selector);
        new AgentPaymentPool(address(registry), address(0), BASE_RATE, DAILY_CAP);
    }

    function test_constructor_reverts_zero_rate() public {
        vm.expectRevert(AgentPaymentPool.InvalidAmount.selector);
        new AgentPaymentPool(address(registry), address(token), 0, DAILY_CAP);
    }

    function test_constructor_default_tier_multipliers() public view {
        assertEq(pool.tierMultipliers(0), 6000);   // poor: 0.6x
        assertEq(pool.tierMultipliers(1), 8000);   // below_avg: 0.8x
        assertEq(pool.tierMultipliers(2), 10000);  // average: 1.0x
        assertEq(pool.tierMultipliers(3), 12000);  // good: 1.2x
        assertEq(pool.tierMultipliers(4), 15000);  // excellent: 1.5x
    }

    // ─── deposit ───────────────────────────────────────────────────────────────

    function test_deposit_increases_pool_balance() public {
        uint256 balanceBefore = pool.poolBalance(address(token));
        token.mint(owner, 100e18);
        token.approve(address(pool), 100e18);
        pool.deposit(address(token), 100e18);
        assertEq(pool.poolBalance(address(token)), balanceBefore + 100e18);
    }

    function test_deposit_emits_event() public {
        token.mint(owner, 50e18);
        token.approve(address(pool), 50e18);
        vm.expectEmit(true, true, false, true);
        emit AgentPaymentPool.PoolDeposited(owner, address(token), 50e18);
        pool.deposit(address(token), 50e18);
    }

    function test_deposit_reverts_zero_amount() public {
        vm.expectRevert(AgentPaymentPool.InvalidAmount.selector);
        pool.deposit(address(token), 0);
    }

    function test_deposit_reverts_when_paused() public {
        pool.pause();
        vm.expectRevert();
        pool.deposit(address(token), 1e18);
    }

    // ─── registerPaymentWallet ─────────────────────────────────────────────────

    function test_register_payment_wallet_success() public {
        address newWallet = makeAddr("newWallet");
        // Agent 0 owner re-registers (wallet already set in setUp, use agent 2)
        vm.prank(agent0Owner);
        registry.register("ipfs://agent2");
        // Agent 2 is agentId 2
        vm.prank(agent0Owner);
        pool.registerPaymentWallet(2, newWallet);
        (,,,,,address wallet) = pool.getPaymentStats(2);
        assertEq(wallet, newWallet);
    }

    function test_register_payment_wallet_emits_event() public {
        vm.prank(agent0Owner);
        registry.register("ipfs://agent2");
        address newWallet = makeAddr("newWallet");
        vm.expectEmit(true, true, false, false);
        emit AgentPaymentPool.PaymentWalletRegistered(2, newWallet);
        vm.prank(agent0Owner);
        pool.registerPaymentWallet(2, newWallet);
    }

    function test_register_payment_wallet_reverts_invalid_agent() public {
        vm.expectRevert(AgentPaymentPool.InvalidAgentId.selector);
        pool.registerPaymentWallet(999, paymentWallet0);
    }

    function test_register_payment_wallet_reverts_zero_address() public {
        vm.prank(agent0Owner);
        registry.register("ipfs://agent2");
        vm.expectRevert(AgentPaymentPool.ZeroAddress.selector);
        vm.prank(agent0Owner);
        pool.registerPaymentWallet(2, address(0));
    }

    function test_register_payment_wallet_reverts_unauthorized() public {
        vm.prank(agent0Owner);
        registry.register("ipfs://agent2");
        vm.expectRevert(AgentPaymentPool.NotAuthorized.selector);
        vm.prank(attacker);
        pool.registerPaymentWallet(2, paymentWallet0);
    }

    // ─── setPaymentRate ────────────────────────────────────────────────────────

    function test_set_payment_rate_success() public {
        pool.setPaymentRate(0, 4); // excellent
        (,,,uint256 rate, uint8 tier,) = pool.getPaymentStats(0);
        assertEq(tier, 4);
        assertEq(rate, (BASE_RATE * 15000) / 10000);
    }

    function test_set_payment_rate_emits_event() public {
        uint256 expectedRate = (BASE_RATE * 15000) / 10000;
        vm.expectEmit(true, false, false, true);
        emit AgentPaymentPool.PaymentRateSet(0, expectedRate, 4);
        pool.setPaymentRate(0, 4);
    }

    function test_set_payment_rate_reverts_invalid_tier() public {
        vm.expectRevert(AgentPaymentPool.InvalidAmount.selector);
        pool.setPaymentRate(0, 5);
    }

    function test_set_payment_rate_reverts_invalid_agent() public {
        vm.expectRevert(AgentPaymentPool.InvalidAgentId.selector);
        pool.setPaymentRate(999, 2);
    }

    function test_set_payment_rate_only_owner() public {
        vm.expectRevert();
        vm.prank(attacker);
        pool.setPaymentRate(0, 2);
    }

    // ─── withdrawPayment ───────────────────────────────────────────────────────

    function test_withdraw_payment_success() public {
        uint256 transferAmount = 100e18;
        uint256 balanceBefore = token.balanceOf(paymentWallet0);

        uint256 rewardAmount = pool.withdrawPayment(0, transferAmount);

        assertGt(rewardAmount, 0);
        assertEq(token.balanceOf(paymentWallet0), balanceBefore + rewardAmount);
    }

    function test_withdraw_payment_emits_event() public {
        vm.expectEmit(true, true, true, false);
        emit AgentPaymentPool.PaymentRewarded(0, paymentWallet0, address(token), 0, 0);
        pool.withdrawPayment(0, 100e18);
    }

    function test_withdraw_payment_updates_stats() public {
        pool.withdrawPayment(0, 100e18);
        (uint256 totalEarned, uint256 lastTs, uint256 dailyEarned,,,) = pool.getPaymentStats(0);
        assertGt(totalEarned, 0);
        assertGt(lastTs, 0);
        assertGt(dailyEarned, 0);
    }

    function test_withdraw_payment_reverts_invalid_agent() public {
        vm.expectRevert(AgentPaymentPool.InvalidAgentId.selector);
        pool.withdrawPayment(999, 100e18);
    }

    function test_withdraw_payment_reverts_no_wallet() public {
        // Register agent without payment wallet
        vm.prank(agent0Owner);
        registry.register("ipfs://agent2");
        pool.setPaymentRate(2, 2);
        // No wallet registered for agent 2
        vm.expectRevert(AgentPaymentPool.PaymentRateNotSet.selector);
        pool.withdrawPayment(2, 100e18);
    }

    function test_withdraw_payment_reverts_no_rate() public {
        // Register agent with wallet but no rate
        vm.prank(agent0Owner);
        registry.register("ipfs://agent2");
        vm.prank(agent0Owner);
        pool.registerPaymentWallet(2, makeAddr("wallet2"));
        // No rate set for agent 2
        vm.expectRevert(AgentPaymentPool.PaymentRateNotSet.selector);
        pool.withdrawPayment(2, 100e18);
    }

    function test_withdraw_payment_only_owner() public {
        vm.expectRevert();
        vm.prank(attacker);
        pool.withdrawPayment(0, 100e18);
    }

    function test_withdraw_payment_reverts_when_paused() public {
        pool.pause();
        vm.expectRevert();
        pool.withdrawPayment(0, 100e18);
    }

    function test_withdraw_payment_enforces_daily_cap() public {
        // Set very low daily cap
        pool.updateDailyCap(1e15); // 0.001 USDm
        pool.withdrawPayment(0, 100e18);
        // Second withdrawal should revert (cap reached)
        vm.expectRevert(AgentPaymentPool.ExceedsWithdrawalCap.selector);
        pool.withdrawPayment(0, 100e18);
    }

    function test_withdraw_payment_daily_cap_resets_after_24h() public {
        pool.updateDailyCap(1e15);
        pool.withdrawPayment(0, 100e18);
        // Advance time by 25 hours
        vm.warp(block.timestamp + 25 hours);
        // Should succeed again
        pool.withdrawPayment(0, 100e18);
    }

    function test_withdraw_payment_reverts_insufficient_pool() public {
        // Drain pool via emergency withdrawal
        uint256 balance = pool.poolBalance(address(token));
        pool.emergencyWithdraw(address(token), owner, balance);
        vm.expectRevert(AgentPaymentPool.InsufficientPoolBalance.selector);
        pool.withdrawPayment(0, 100e18);
    }

    // ─── Tier multiplier math ──────────────────────────────────────────────────

    function test_tier_0_poor_multiplier() public {
        pool.setPaymentRate(0, 0);
        (,,,uint256 rate,,) = pool.getPaymentStats(0);
        assertEq(rate, (BASE_RATE * 6000) / 10000);
    }

    function test_tier_4_excellent_multiplier() public {
        pool.setPaymentRate(0, 4);
        (,,,uint256 rate,,) = pool.getPaymentStats(0);
        assertEq(rate, (BASE_RATE * 15000) / 10000);
    }

    function test_reward_scales_with_transfer_amount() public {
        // Use amounts well below the 100e18 cap so rewards scale linearly
        uint256 reward10 = pool.withdrawPayment(0, 10e18);
        // Reset daily tracking by advancing time
        vm.warp(block.timestamp + 25 hours);
        uint256 reward50 = pool.withdrawPayment(0, 50e18);
        assertGt(reward50, reward10);
    }

    function test_reward_capped_at_100_ether_factor() public {
        // Transfer amounts above 100e18 should be capped
        uint256 reward100 = pool.withdrawPayment(0, 100e18);
        vm.warp(block.timestamp + 25 hours);
        uint256 reward1000 = pool.withdrawPayment(0, 1000e18);
        // Both should be equal since 1000e18 > 100e18 cap
        assertEq(reward100, reward1000);
    }

    // ─── Admin functions ───────────────────────────────────────────────────────

    function test_update_base_rate() public {
        pool.updateBaseRate(0.01e18);
        assertEq(pool.basePaymentRate(), 0.01e18);
    }

    function test_update_base_rate_reverts_zero() public {
        vm.expectRevert(AgentPaymentPool.InvalidAmount.selector);
        pool.updateBaseRate(0);
    }

    function test_update_daily_cap() public {
        pool.updateDailyCap(50e18);
        assertEq(pool.dailyCapPerAgent(), 50e18);
        // Check event
    }

    function test_update_tier_multipliers() public {
        uint256[5] memory newMultipliers = [uint256(5000), 7000, 10000, 13000, 16000];
        pool.updateTierMultipliers(newMultipliers);
        assertEq(pool.tierMultipliers(0), 5000);
        assertEq(pool.tierMultipliers(4), 16000);
    }

    // ─── Emergency controls ────────────────────────────────────────────────────

    function test_pause_and_unpause() public {
        pool.pause();
        assertTrue(pool.paused());
        pool.unpause();
        assertFalse(pool.paused());
    }

    function test_emergency_withdraw() public {
        uint256 balance = pool.poolBalance(address(token));
        pool.emergencyWithdraw(address(token), owner, balance);
        assertEq(pool.poolBalance(address(token)), 0);
    }

    function test_emergency_withdraw_reverts_zero_address() public {
        vm.expectRevert(AgentPaymentPool.ZeroAddress.selector);
        pool.emergencyWithdraw(address(token), address(0), 1e18);
    }

    function test_emergency_withdraw_only_owner() public {
        vm.expectRevert();
        vm.prank(attacker);
        pool.emergencyWithdraw(address(token), attacker, 1e18);
    }

    // ─── getPaymentStats ───────────────────────────────────────────────────────

    function test_get_payment_stats_initial() public view {
        (
            uint256 totalEarned,
            uint256 lastTs,
            uint256 dailyEarned,
            uint256 rate,
            uint8 tier,
            address wallet
        ) = pool.getPaymentStats(0);

        assertEq(totalEarned, 0);
        assertEq(lastTs, 0);
        assertEq(dailyEarned, 0);
        assertGt(rate, 0);
        assertEq(tier, 3); // set in setUp
        assertEq(wallet, paymentWallet0);
    }

    // ─── poolBalance ───────────────────────────────────────────────────────────

    function test_pool_balance_reflects_deposits() public view {
        assertEq(pool.poolBalance(address(token)), POOL_FUND);
    }

    // ─── Reentrancy guard ──────────────────────────────────────────────────────

    function test_reentrancy_guard_on_withdraw() public {
        // Deploy reentrant token that attempts a reentrant call during transfer
        ReentrantToken reentrantToken = new ReentrantToken(address(0));
        AgentPaymentPool reentrantPool = new AgentPaymentPool(
            address(registry),
            address(reentrantToken),
            BASE_RATE,
            DAILY_CAP
        );
        reentrantToken.setPoolAddress(address(reentrantPool));
        reentrantToken.mint(owner, 1000e18);
        reentrantToken.approve(address(reentrantPool), 1000e18);
        reentrantPool.deposit(address(reentrantToken), 1000e18);
        reentrantPool.setPaymentRate(0, 3);
        vm.prank(agent0Owner);
        reentrantPool.registerPaymentWallet(0, paymentWallet0);

        // The outer withdrawPayment completes, but the inner reentrant call is blocked.
        // Verify: only ONE reward is paid (the reentrant call was blocked by ReentrancyGuard).
        uint256 balanceBefore = reentrantToken.balanceOf(paymentWallet0);
        reentrantPool.withdrawPayment(0, 10e18);
        uint256 balanceAfter = reentrantToken.balanceOf(paymentWallet0);

        // Only one reward should have been transferred (not two)
        uint256 singleReward = (BASE_RATE * 12000 / 10000) * 10e18 / 1e18;
        assertEq(balanceAfter - balanceBefore, singleReward);
    }
}


// ─── Mock ERC20 ────────────────────────────────────────────────────────────────

contract MockERC20 {
    string public name;
    string public symbol;
    uint8 public decimals;
    uint256 public totalSupply;

    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);

    constructor(string memory _name, string memory _symbol, uint8 _decimals) {
        name = _name;
        symbol = _symbol;
        decimals = _decimals;
    }

    function mint(address to, uint256 amount) external {
        balanceOf[to] += amount;
        totalSupply += amount;
        emit Transfer(address(0), to, amount);
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function transfer(address to, uint256 amount) external virtual returns (bool) {
        require(balanceOf[msg.sender] >= amount, "Insufficient");
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        emit Transfer(msg.sender, to, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        require(allowance[from][msg.sender] >= amount, "Allowance exceeded");
        require(balanceOf[from] >= amount, "Insufficient");
        allowance[from][msg.sender] -= amount;
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        emit Transfer(from, to, amount);
        return true;
    }
}


// ─── Reentrant Token (for reentrancy test) ─────────────────────────────────────

contract ReentrantToken is MockERC20 {
    address public poolAddress;
    bool private _attacking;

    constructor(address _pool) MockERC20("RToken", "RTK", 18) {
        poolAddress = _pool;
    }

    function setPoolAddress(address _pool) external {
        poolAddress = _pool;
    }

    function transfer(address to, uint256 amount) external virtual override returns (bool) {
        require(balanceOf[msg.sender] >= amount, "Insufficient");
        if (!_attacking && to != address(0) && poolAddress != address(0)) {
            _attacking = true;
            // Attempt reentrant call into the same pool
            try AgentPaymentPool(poolAddress).withdrawPayment(0, 10e18) {} catch {}
            _attacking = false;
        }
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        emit Transfer(msg.sender, to, amount);
        return true;
    }
}
