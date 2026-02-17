// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/structs/EnumerableSet.sol";
import "./interfaces/ITEERegistry.sol";
import "./interfaces/IIdentityRegistry.sol";
import "./interfaces/ITEEVerifier.sol";

/**
 * @title TEERegistry
 * @notice Manages TEE attestations and public keys for agents
 * @dev Integrates with identity registry for agent ownership verification
 * @dev Based on actual ERC-8004 TEE Agent implementation
 */
contract TEERegistry is Ownable, ReentrancyGuard, ITEERegistry {
    using EnumerableSet for EnumerableSet.AddressSet;

    IIdentityRegistry public immutable identityRegistry;

    // Whitelisted verifiers (e.g., Automata DCAP verifier)
    mapping(address => Verifier) private _verifiers;
    
    // Agent keys (one agent can have multiple keys from different TEE instances)
    mapping(uint256 => EnumerableSet.AddressSet) private _agentKeys;
    mapping(address => Key) private _keys;

    constructor(address _identityRegistry) Ownable(msg.sender) {
        if (_identityRegistry == address(0)) revert InvalidVerifier();
        identityRegistry = IIdentityRegistry(_identityRegistry);
    }

    /**
     * @notice Add whitelisted TEE verifier
     * @param verifier Verifier contract address (e.g., Automata DCAP)
     * @param teeArch TEE architecture identifier
     */
    function addVerifier(address verifier, bytes32 teeArch) external onlyOwner {
        if (verifier == address(0)) revert InvalidVerifier();
        _verifiers[verifier] = Verifier({ teeArch: teeArch });
        emit VerifierAdded(verifier, teeArch);
    }

    /**
     * @notice Remove verifier from whitelist
     * @param verifier Verifier address to remove
     */
    function removeVerifier(address verifier) external onlyOwner {
        if (verifier == address(0)) revert InvalidVerifier();
        delete _verifiers[verifier];
        emit VerifierRemoved(verifier);
    }

    /**
     * @notice Register TEE-derived public key with attestation
     * @param agentId Agent ID from IdentityRegistry
     * @param teeArch TEE architecture
     * @param codeMeasurement Hash of code running in TEE
     * @param pubkey Public key address derived in TEE
     * @param codeConfigUri Link to code configuration
     * @param verifier Verifier contract to validate proof
     * @param proof Attestation proof bytes
     */
    function addKey(
        uint256 agentId,
        bytes32 teeArch,
        bytes32 codeMeasurement,
        address pubkey,
        string calldata codeConfigUri,
        address verifier,
        bytes calldata proof
    ) external nonReentrant {
        // Verify agent exists
        if (!identityRegistry.exists(agentId)) revert InvalidAgentId();
        
        // Verify caller is authorized to manage agent
        if (!_isAgentAuthorized(agentId)) revert NotAuthorized();
        
        // Verify verifier is whitelisted
        if (_verifiers[verifier].teeArch == bytes32(0)) revert VerifierNotWhitelisted();
        
        // Verify key doesn't already exist
        if (_keys[pubkey].verifier != address(0)) revert KeyAlreadyExists();

        // Call verifier contract to validate attestation proof
        // The verifier validates TEE attestation, measurement, and pubkey
        try ITEEVerifier(verifier).verifyAttestation(proof) returns (bool success, bytes memory) {
            if (!success) revert InvalidAttestation();
        } catch {
            revert InvalidAttestation();
        }
        
        _keys[pubkey] = Key({
            teeArch: teeArch,
            codeMeasurement: codeMeasurement,
            pubkey: abi.encodePacked(pubkey),
            codeConfigUri: codeConfigUri,
            verifier: verifier,
            registeredAt: block.timestamp
        });

        _agentKeys[agentId].add(pubkey);

        emit KeyAdded(agentId, teeArch, codeMeasurement, pubkey, codeConfigUri, verifier);
    }

    /**
     * @notice Remove key from agent
     * @param agentId The agent ID
     * @param pubkey The public key address to remove
     */
    function removeKey(uint256 agentId, address pubkey) external nonReentrant {
        // Verify caller is authorized to manage agent
        if (!_isAgentAuthorized(agentId)) revert NotAuthorized();
        
        if (!_agentKeys[agentId].contains(pubkey)) revert KeyNotFound();
        
        _agentKeys[agentId].remove(pubkey);
        delete _keys[pubkey];
        
        emit KeyRemoved(agentId, pubkey);
    }

    /**
     * @notice Get key details
     * @param agentId The agent ID
     * @param pubkey The public key address
     * @return key The key details
     */
    function getKey(uint256 agentId, address pubkey) external view returns (Key memory) {
        if (!_agentKeys[agentId].contains(pubkey)) revert KeyNotFound();
        return _keys[pubkey];
    }

    /**
     * @notice Check if agent has registered key
     * @param agentId The agent ID
     * @param pubkey The public key address
     * @return result True if key exists
     */
    function hasKey(uint256 agentId, address pubkey) external view returns (bool result) {
        return _agentKeys[agentId].contains(pubkey);
    }

    /**
     * @notice Get number of keys for agent
     * @param agentId The agent ID
     * @return count The number of keys
     */
    function getKeyCount(uint256 agentId) external view returns (uint256 count) {
        return _agentKeys[agentId].length();
    }

    /**
     * @notice Get key at index for agent
     * @param agentId The agent ID
     * @param index The key index
     * @return pubkey The public key address at index
     */
    function getKeyAtIndex(uint256 agentId, uint256 index) external view returns (address pubkey) {
        return _agentKeys[agentId].at(index);
    }

    /**
     * @notice Check if address is whitelisted verifier
     * @param verifier The verifier address
     * @return result True if whitelisted
     */
    function isVerifier(address verifier) external view returns (bool result) {
        return _verifiers[verifier].teeArch != bytes32(0);
    }

    /**
     * @notice Get verifier info
     * @param verifier The verifier address
     * @return verifierInfo The verifier information
     */
    function verifiers(address verifier) external view returns (Verifier memory verifierInfo) {
        return _verifiers[verifier];
    }

    /**
     * @notice Get all keys for an agent (WARNING: unbounded)
     * @param agentId The agent ID
     * @return keys Array of public key addresses
     */
    function getAgentKeys(uint256 agentId) external view returns (address[] memory keys) {
        uint256 count = _agentKeys[agentId].length();
        keys = new address[](count);
        
        for (uint256 i = 0; i < count; i++) {
            keys[i] = _agentKeys[agentId].at(i);
        }
    }

    /**
     * @notice Get keys for an agent with pagination to prevent Gas DoS
     * @param agentId The agent ID
     * @param start The starting index
     * @param limit The maximum number of keys to return
     * @return keys Array of public key addresses
     * @return nextOffset The next offset to use (or 0 if finished)
     */
    function getAgentKeys(uint256 agentId, uint256 start, uint256 limit) external view returns (address[] memory keys, uint256 nextOffset) {
        uint256 total = _agentKeys[agentId].length();
        
        if (start >= total) {
            return (new address[](0), 0);
        }

        uint256 end = start + limit;
        if (end > total) {
            end = total;
        }

        uint256 count = end - start;
        keys = new address[](count);
        
        for (uint256 i = 0; i < count; i++) {
            keys[i] = _agentKeys[agentId].at(start + i);
        }

        nextOffset = end < total ? end : 0;
    }

    /**
     * @notice Get key registration time
     * @param pubkey The public key address
     * @return registeredAt Registration timestamp
     */
    function getKeyRegistrationTime(address pubkey) external view returns (uint256 registeredAt) {
        if (_keys[pubkey].verifier == address(0)) revert KeyNotFound();
        return _keys[pubkey].registeredAt;
    }

    /**
     * @notice Check if caller is authorized to manage agent
     * @param agentId The agent ID
     * @return authorized True if authorized
     */
    function _isAgentAuthorized(uint256 agentId) internal view returns (bool authorized) {
        address owner = identityRegistry.ownerOf(agentId);
        
        return (
            msg.sender == owner ||
            identityRegistry.isApprovedForAll(owner, msg.sender) ||
            msg.sender == identityRegistry.getApproved(agentId)
        );
    }
}
