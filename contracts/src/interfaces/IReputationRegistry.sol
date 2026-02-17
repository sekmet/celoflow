// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IReputationRegistry
 * @notice Interface for the ReputationRegistry contract
 */
interface IReputationRegistry {
    enum FeedbackStatus { Active, Revoked }

    struct Feedback {
        int128 value;
        uint8 valueDecimals;
        string tag1;
        string tag2;
        address client;
        uint256 timestamp;
        bool isRevoked;
        string feedbackURI;
        bytes32 feedbackHash;
    }

    event FeedbackGiven(
        uint256 indexed agentId,
        address indexed client,
        int128 value,
        uint8 valueDecimals,
        string tag1,
        string tag2
    );

    event FeedbackRevoked(
        uint256 indexed agentId,
        address indexed client,
        uint64 feedbackIndex
    );

    event ResponseAppended(
        uint256 indexed agentId,
        address indexed client,
        uint64 feedbackIndex,
        string responseURI,
        bytes32 responseHash
    );

    error InvalidAgentId();
    error InvalidFeedbackIndex();
    error AlreadyRevoked();
    error NotAuthorized();
    error SelfFeedback();
    error InvalidValue();
    error InvalidDecimals();

    function giveFeedback(
        uint256 agentId,
        int128 value,
        uint8 valueDecimals,
        string memory tag1,
        string memory tag2,
        string memory endpoint,
        string memory feedbackURI,
        bytes32 feedbackHash
    ) external;
    
    function getSummary(
        uint256 agentId,
        address[] memory clientAddresses,
        string memory tag1,
        string memory tag2
    ) external view returns (
        uint64 count,
        int128 summaryValue,
        uint8 summaryValueDecimals
    );

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
    );

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
    );
    
    function getClients(uint256 agentId) external view returns (address[] memory clients);
    
    function revokeFeedback(
        uint256 agentId,
        address clientAddress,
        uint64 feedbackIndex
    ) external;
    
    function appendResponse(
        uint256 agentId,
        address clientAddress,
        uint64 feedbackIndex,
        string memory responseURI,
        bytes32 responseHash
    ) external;
    
    function getFeedbackCount(uint256 agentId, address clientAddress) external view returns (uint64 count);
    
    function hasFeedback(uint256 agentId, address clientAddress) external view returns (bool result);
}
