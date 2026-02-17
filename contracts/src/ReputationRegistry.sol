// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "./interfaces/IReputationRegistry.sol";
import "./interfaces/IIdentityRegistry.sol";

/**
 * @title ReputationRegistry
 * @notice Feedback system for agent reputation following ERC-8004 specification
 * @dev Uses actual ERC-8004 reputation spec with fixed-point math
 */
contract ReputationRegistry is ReentrancyGuard, IReputationRegistry {
    // agentId => client => feedbackIndex => Feedback
    mapping(uint256 => mapping(address => mapping(uint64 => Feedback))) private _feedback;
    
    // agentId => client => feedback count
    mapping(uint256 => mapping(address => uint64)) private _feedbackCount;
    
    // agentId => all clients who gave feedback
    mapping(uint256 => address[]) private _clients;
    mapping(uint256 => mapping(address => bool)) private _isClient;

    IIdentityRegistry public immutable identityRegistry;

    constructor(address _identityRegistry) {
        if (_identityRegistry == address(0)) revert InvalidAgentId();
        identityRegistry = IIdentityRegistry(_identityRegistry);
    }

    /**
     * @notice Submit feedback for an agent
     * @param agentId The agent ID
     * @param value Feedback score (-100 to 100)
     * @param valueDecimals Decimal precision (0-18)
     * @param tag1 Primary category
     * @param tag2 Secondary category
     * @param endpoint Service endpoint (optional)
     * @param feedbackURI IPFS link to details
     * @param feedbackHash Content hash
     */
    function giveFeedback(
        uint256 agentId,
        int128 value,
        uint8 valueDecimals,
        string memory tag1,
        string memory tag2,
        string memory endpoint,
        string memory feedbackURI,
        bytes32 feedbackHash
    ) external nonReentrant {
        // Verify agent exists
        if (!identityRegistry.exists(agentId)) revert InvalidAgentId();
        
        // Prevent self-feedback
        address agentOwner = identityRegistry.ownerOf(agentId);
        if (msg.sender == agentOwner) revert SelfFeedback();
        
        // Validate value and decimals
        if (valueDecimals > 18) revert InvalidDecimals();
        if (value == 0) revert InvalidValue();
        
        uint64 index = _feedbackCount[agentId][msg.sender];
        
        _feedback[agentId][msg.sender][index] = Feedback({
            value: value,
            valueDecimals: valueDecimals,
            tag1: tag1,
            tag2: tag2,
            client: msg.sender,
            timestamp: block.timestamp,
            isRevoked: false,
            feedbackURI: feedbackURI,
            feedbackHash: feedbackHash
        });
        
        _feedbackCount[agentId][msg.sender]++;
        
        // Track client
        if (!_isClient[agentId][msg.sender]) {
            _clients[agentId].push(msg.sender);
            _isClient[agentId][msg.sender] = true;
        }
        
        emit FeedbackGiven(agentId, msg.sender, value, valueDecimals, tag1, tag2);
    }

    /**
     * @notice Get feedback summary (average score) - WARNING: Unbounded loop
     * @param agentId The agent ID
     * @param clientAddresses Specific clients to include (empty for all)
     * @param tag1 Filter by primary tag (empty for all)
     * @param tag2 Filter by secondary tag (empty for all)
     * @return count Number of feedback entries
     * @return summaryValue Average value
     * @return summaryValueDecimals Average value decimals
     */
    function getSummary(
        uint256 agentId,
        address[] memory clientAddresses,
        string memory tag1,
        string memory tag2
    ) external view returns (
        uint64 count,
        int128 summaryValue,
        uint8 summaryValueDecimals
    ) {
        return getSummaryInternal(agentId, clientAddresses, tag1, tag2, 0, 0);
    }

    /**
     * @notice Get feedback summary with pagination to prevent Gas DoS
     * @param agentId The agent ID
     * @param clientAddresses Specific clients to include (empty for all)
     * @param tag1 Filter by primary tag (empty for all)
     * @param tag2 Filter by secondary tag (empty for all)
     * @param limit Maximum number of clients to process (0 for all, but risky)
     * @param offset Client index offset
     * @return count Number of feedback entries found in this batch
     * @return summaryValue Average value of this batch
     * @return summaryValueDecimals Average value decimals
     * @return nextOffset Next offset to use
     */
    function getSummaryPaged(
        uint256 agentId,
        address[] memory clientAddresses,
        string memory tag1,
        string memory tag2,
        uint256 limit,
        uint256 offset
    ) external view returns (
        uint64 count,
        int128 summaryValue,
        uint8 summaryValueDecimals,
        uint256 nextOffset
    ) {
        (count, summaryValue, summaryValueDecimals) = getSummaryInternal(agentId, clientAddresses, tag1, tag2, limit, offset);
        
        // Calculate next offset
        uint256 totalClients = clientAddresses.length > 0 ? clientAddresses.length : _clients[agentId].length;
        if (limit > 0 && offset + limit < totalClients) {
            nextOffset = offset + limit;
        } else {
            nextOffset = 0;
        }
    }

    function getSummaryInternal(
        uint256 agentId,
        address[] memory clientAddresses,
        string memory tag1,
        string memory tag2,
        uint256 limit,
        uint256 offset
    ) internal view returns (
        uint64 count,
        int128 summaryValue,
        uint8 summaryValueDecimals
    ) {
        if (!identityRegistry.exists(agentId)) revert InvalidAgentId();
        
        int256 sum = 0;
        count = 0;
        uint8 maxDecimals = 0;
        
        address[] memory clients;
        if (clientAddresses.length > 0) {
            clients = clientAddresses;
        } else {
            clients = _clients[agentId];
        }

        uint256 end = clients.length;
        if (limit > 0 && offset + limit < end) {
            end = offset + limit;
        }
        
        for (uint256 i = offset; i < end; i++) {
            address client = clients[i];
            uint64 feedbackCount = _feedbackCount[agentId][client];
            
            for (uint64 j = 0; j < feedbackCount; j++) {
                Feedback memory fb = _feedback[agentId][client][j];
                
                if (!fb.isRevoked) {
                    // Apply tag filters if specified
                    bool matchesTag1 = bytes(tag1).length == 0 || 
                        keccak256(bytes(fb.tag1)) == keccak256(bytes(tag1));
                    bool matchesTag2 = bytes(tag2).length == 0 || 
                        keccak256(bytes(fb.tag2)) == keccak256(bytes(tag2));
                    
                    if (matchesTag1 && matchesTag2) {
                        if (fb.valueDecimals > maxDecimals) {
                            // Scale up existing sum to new precision
                            sum = sum * int256(10 ** (uint256(fb.valueDecimals) - uint256(maxDecimals)));
                            maxDecimals = fb.valueDecimals;
                            
                            // Add new value (already at new precision)
                            sum += int256(fb.value);
                        } else {
                            // Scale up new value to existing precision
                            int256 normalizedValue = int256(fb.value) * 
                                int256(10 ** (uint256(maxDecimals) - uint256(fb.valueDecimals)));
                            sum += normalizedValue;
                        }
                        
                        count++;
                    }
                }
            }
        }
        
        if (count > 0) {
            summaryValue = int128(sum / int256(uint256(count)));
            summaryValueDecimals = maxDecimals;
        } else {
            summaryValue = int128(0);
            summaryValueDecimals = 0;
        }
    }

    /**
     * @notice Read specific feedback
     * @param agentId The agent ID
     * @param clientAddress The client address
     * @param feedbackIndex The feedback index
     * @return value Feedback value
     * @return valueDecimals Value decimals
     * @return tag1 Primary tag
     * @return tag2 Secondary tag
     * @return isRevoked Revocation status
     */
    function readFeedback(
        uint256 agentId,
        address clientAddress,
        uint64 feedbackIndex
    ) external view returns (
        int128 value,
        uint8 valueDecimals,
        string memory tag1,
        string memory tag2,
        bool isRevoked
    ) {
        if (!identityRegistry.exists(agentId)) revert InvalidAgentId();
        if (feedbackIndex >= _feedbackCount[agentId][clientAddress]) revert InvalidFeedbackIndex();
        
        Feedback memory fb = _feedback[agentId][clientAddress][feedbackIndex];
        return (fb.value, fb.valueDecimals, fb.tag1, fb.tag2, fb.isRevoked);
    }

    /**
     * @notice Get all clients who gave feedback
     * @param agentId The agent ID
     * @return clients Array of client addresses
     */
    function getClients(uint256 agentId) external view returns (address[] memory clients) {
        if (!identityRegistry.exists(agentId)) revert InvalidAgentId();
        return _clients[agentId];
    }

    /**
     * @notice Revoke feedback (client only)
     * @param agentId The agent ID
     * @param clientAddress The client address
     * @param feedbackIndex The feedback index
     */
    function revokeFeedback(
        uint256 agentId,
        address clientAddress,
        uint64 feedbackIndex
    ) external nonReentrant {
        if (!identityRegistry.exists(agentId)) revert InvalidAgentId();
        if (msg.sender != clientAddress) revert NotAuthorized();
        if (feedbackIndex >= _feedbackCount[agentId][clientAddress]) revert InvalidFeedbackIndex();
        if (_feedback[agentId][clientAddress][feedbackIndex].isRevoked) revert AlreadyRevoked();
        
        _feedback[agentId][clientAddress][feedbackIndex].isRevoked = true;
        
        emit FeedbackRevoked(agentId, clientAddress, feedbackIndex);
    }

    /**
     * @notice Append response to feedback
     * @param agentId The agent ID
     * @param clientAddress The client address
     * @param feedbackIndex The feedback index
     * @param responseURI IPFS link to response
     * @param responseHash Response content hash
     */
    function appendResponse(
        uint256 agentId,
        address clientAddress,
        uint64 feedbackIndex,
        string memory responseURI,
        bytes32 responseHash
    ) external nonReentrant {
        if (!identityRegistry.exists(agentId)) revert InvalidAgentId();
        if (feedbackIndex >= _feedbackCount[agentId][clientAddress]) revert InvalidFeedbackIndex();
        
        // Only agent owner can append responses
        address agentOwner = identityRegistry.ownerOf(agentId);
        if (msg.sender != agentOwner) revert NotAuthorized();
        
        // Store response in feedback URI (simplified approach)
        _feedback[agentId][clientAddress][feedbackIndex].feedbackURI = responseURI;
        _feedback[agentId][clientAddress][feedbackIndex].feedbackHash = responseHash;
        
        emit ResponseAppended(agentId, clientAddress, feedbackIndex, responseURI, responseHash);
    }

    /**
     * @notice Get feedback count for a client
     * @param agentId The agent ID
     * @param clientAddress The client address
     * @return count Number of feedback entries
     */
    function getFeedbackCount(uint256 agentId, address clientAddress) external view returns (uint64 count) {
        if (!identityRegistry.exists(agentId)) revert InvalidAgentId();
        return _feedbackCount[agentId][clientAddress];
    }

    /**
     * @notice Check if client has given feedback
     * @param agentId The agent ID
     * @param clientAddress The client address
     * @return result True if client has given feedback
     */
    function hasFeedback(uint256 agentId, address clientAddress) external view returns (bool result) {
        if (!identityRegistry.exists(agentId)) revert InvalidAgentId();
        return _feedbackCount[agentId][clientAddress] > 0;
    }
}
