// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/IERC721.sol";

/**
 * @title IIdentityRegistry
 * @notice Interface for the IdentityRegistry contract
 */
interface IIdentityRegistry is IERC721 {
    struct MetadataEntry {
        string key;
        bytes value;
    }

    event Registered(uint256 indexed agentId, string tokenURI, address indexed owner);
    event MetadataSet(uint256 indexed agentId, string indexed indexedKey, string key, bytes value);
    event UriUpdated(uint256 indexed agentId, string newUri, address indexed updatedBy);
    event AgentWalletSet(uint256 indexed agentId, address indexed newWallet, address indexed updatedBy);
    event AgentWalletUnset(uint256 indexed agentId, address indexed previousWallet);

    error NotAuthorized();
    error InvalidAgentId();
    error AgentWalletAlreadySet();
    error AgentWalletNotSet();

    function register() external returns (uint256 agentId);
    function register(string memory tokenUri) external returns (uint256 agentId);
    function register(string memory tokenUri, MetadataEntry[] memory metadata) external returns (uint256 agentId);
    
    function getMetadata(uint256 agentId, string memory key) external view returns (bytes memory);
    function setMetadata(uint256 agentId, string memory key, bytes memory value) external;
    
    function setAgentUri(uint256 agentId, string calldata newUri) external;
    
    function getAgentWallet(uint256 agentId) external view returns (address wallet);
    function setAgentWallet(uint256 agentId, address newWallet) external;
    function unsetAgentWallet(uint256 agentId) external;
    
    function totalSupply() external view returns (uint256 count);
    
    function exists(uint256 agentId) external view returns (bool result);
}
