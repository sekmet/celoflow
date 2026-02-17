// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title ITEEVerifier
 * @notice Interface for TEE Attestation Verifier contracts (e.g., Automata DCAP)
 */
interface ITEEVerifier {
    /**
     * @notice Verify a TEE attestation
     * @param proof The attestation proof bytes
     * @return success True if verification succeeded
     * @return reportData Decoded report data (optional, depends on implementation)
     */
    function verifyAttestation(bytes calldata proof) external view returns (bool success, bytes memory reportData);
}
