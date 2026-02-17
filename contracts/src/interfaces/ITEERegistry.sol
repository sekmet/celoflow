// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title ITEERegistry
 * @notice Interface for the TEERegistry contract
 */
interface ITEERegistry {
    struct Verifier {
        bytes32 teeArch;
    }

    struct Key {
        bytes32 teeArch;
        bytes32 codeMeasurement;
        bytes pubkey;
        string codeConfigUri;
        address verifier;
        uint256 registeredAt;
    }

    event VerifierAdded(address indexed verifier, bytes32 teeArch);
    event VerifierRemoved(address indexed verifier);
    event KeyAdded(
        uint256 indexed agentId,
        bytes32 teeArch,
        bytes32 codeMeasurement,
        address indexed pubkey,
        string codeConfigUri,
        address indexed verifier
    );
    event KeyRemoved(uint256 indexed agentId, address indexed pubkey);

    error InvalidVerifier();
    error VerifierNotWhitelisted();
    error KeyAlreadyExists();
    error KeyNotFound();
    error NotAuthorized();
    error InvalidAgentId();
    error InvalidAttestation();

    function addVerifier(address verifier, bytes32 teeArch) external;
    function removeVerifier(address verifier) external;
    
    function addKey(
        uint256 agentId,
        bytes32 teeArch,
        bytes32 codeMeasurement,
        address pubkey,
        string calldata codeConfigUri,
        address verifier,
        bytes calldata proof
    ) external;
    
    function removeKey(uint256 agentId, address pubkey) external;
    
    function getKey(uint256 agentId, address pubkey) external view returns (Key memory);
    function hasKey(uint256 agentId, address pubkey) external view returns (bool result);
    function getKeyCount(uint256 agentId) external view returns (uint256 count);
    function getKeyAtIndex(uint256 agentId, uint256 index) external view returns (address pubkey);
    function getAgentKeys(uint256 agentId) external view returns (address[] memory keys);
    function getAgentKeys(uint256 agentId, uint256 start, uint256 limit) external view returns (address[] memory keys, uint256 nextOffset);
    
    function isVerifier(address verifier) external view returns (bool result);
    function verifiers(address verifier) external view returns (Verifier memory verifierInfo);
    function getKeyRegistrationTime(address pubkey) external view returns (uint256 registeredAt);
}
