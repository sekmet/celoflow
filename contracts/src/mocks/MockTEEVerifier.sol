// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../interfaces/ITEEVerifier.sol";

/**
 * @title MockTEEVerifier
 * @notice Mock TEE verifier for local Anvil testing
 * @dev Always returns success — DO NOT use in production
 */
contract MockTEEVerifier is ITEEVerifier {
    function verifyAttestation(bytes calldata) external pure override returns (bool success, bytes memory reportData) {
        return (true, "");
    }
}
