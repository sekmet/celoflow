// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import "@openzeppelin/contracts/token/ERC721/IERC721.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "./interfaces/IIdentityRegistry.sol";

/**
 * @title IdentityRegistry
 * @notice ERC-721 based agent identity registry for ERC-8004
 * @dev Simplified production design without upgradeability complexity
 * @dev Based on actual ERC-8004 TEE Agent implementation
 */
contract IdentityRegistry is ERC721URIStorage, Ownable, ReentrancyGuard, IIdentityRegistry {
    uint256 private _lastId = 0;

    // agentId => key => value (arbitrary metadata storage)
    mapping(uint256 => mapping(string => bytes)) private _metadata;

    // agentId => agent wallet address (for proving control)
    mapping(uint256 => address) private _agentWallets;



    constructor() ERC721("AgentIdentity", "AID") Ownable(msg.sender) {}

    /**
     * @notice Register agent without URI (sets empty URI)
     * @return agentId The newly created agent ID
     */
    function register() external nonReentrant returns (uint256 agentId) {
        agentId = _lastId++;
        _safeMint(msg.sender, agentId);
        emit Registered(agentId, "", msg.sender);
    }

    /**
     * @notice Register agent with token URI
     * @param tokenUri IPFS or HTTP URL pointing to agent metadata
     * @return agentId The newly created agent ID
     */
    function register(string memory tokenUri) external nonReentrant returns (uint256 agentId) {
        agentId = _lastId++;
        _safeMint(msg.sender, agentId);
        _setTokenURI(agentId, tokenUri);
        emit Registered(agentId, tokenUri, msg.sender);
    }

    /**
     * @notice Register agent with URI and initial metadata
     * @param tokenUri Agent metadata URI
     * @param metadata Initial key-value pairs
     * @return agentId The newly created agent ID
     */
    function register(
        string memory tokenUri,
        MetadataEntry[] memory metadata
    ) external nonReentrant returns (uint256 agentId) {
        agentId = _lastId++;
        _safeMint(msg.sender, agentId);
        _setTokenURI(agentId, tokenUri);
        emit Registered(agentId, tokenUri, msg.sender);

        for (uint256 i = 0; i < metadata.length; i++) {
            _metadata[agentId][metadata[i].key] = metadata[i].value;
            emit MetadataSet(agentId, metadata[i].key, metadata[i].key, metadata[i].value);
        }
    }

    /**
     * @notice Get metadata value for an agent
     * @param agentId The agent ID
     * @param key The metadata key
     * @return value The metadata value
     */
    function getMetadata(uint256 agentId, string memory key) external view returns (bytes memory) {
        if (!_exists(agentId)) revert InvalidAgentId();
        return _metadata[agentId][key];
    }

    /**
     * @notice Set metadata (owner, approved, or operator only)
     * @param agentId The agent ID
     * @param key The metadata key
     * @param value The metadata value
     */
    function setMetadata(uint256 agentId, string memory key, bytes memory value) external {
        if (!_isAuthorized(agentId)) revert NotAuthorized();
        _metadata[agentId][key] = value;
        emit MetadataSet(agentId, key, key, value);
    }

    /**
     * @notice Update agent URI (owner, approved, or operator only)
     * @param agentId The agent ID
     * @param newUri The new token URI
     */
    function setAgentUri(uint256 agentId, string calldata newUri) external {
        if (!_isAuthorized(agentId)) revert NotAuthorized();
        _setTokenURI(agentId, newUri);
        emit UriUpdated(agentId, newUri, msg.sender);
    }

    /**
     * @notice Get the agent wallet address
     * @param agentId The agent ID
     * @return wallet The agent wallet address
     */
    function getAgentWallet(uint256 agentId) external view returns (address wallet) {
        if (!_exists(agentId)) revert InvalidAgentId();
        return _agentWallets[agentId];
    }

    /**
     * @notice Set agent wallet (for proving control)
     * @param agentId The agent ID
     * @param newWallet The new wallet address
     */
    function setAgentWallet(uint256 agentId, address newWallet) external {
        if (!_isAuthorized(agentId)) revert NotAuthorized();
        if (newWallet == address(0)) revert AgentWalletAlreadySet();
        if (_agentWallets[agentId] != address(0)) revert AgentWalletAlreadySet();
        
        _agentWallets[agentId] = newWallet;
        emit AgentWalletSet(agentId, newWallet, msg.sender);
    }

    /**
     * @notice Unset agent wallet (called on transfer)
     * @param agentId The agent ID
     */
    function unsetAgentWallet(uint256 agentId) external {
        if (!_isAuthorized(agentId)) revert NotAuthorized();
        if (_agentWallets[agentId] == address(0)) revert AgentWalletNotSet();
        
        address previousWallet = _agentWallets[agentId];
        delete _agentWallets[agentId];
        emit AgentWalletUnset(agentId, previousWallet);
    }

    /**
     * @notice Get total number of registered agents
     * @return count The total agent count
     */
    function totalSupply() external view returns (uint256 count) {
        return _lastId;
    }

    /**
     * @notice Check if agent exists
     * @param agentId The agent ID to check
     * @return exists True if agent exists
     */


    // ... (keep intermediate functions same if no changes needed, but I'll implement the fix for _exists collision here if it was global)
    // Actually, the collision was in `exists(uint256 agentId) returns (bool exists)`.
    // I should rename the return variable to `ok` or `result` or just remove the name.

    /**
     * @notice Check if agent exists
     * @param agentId The agent ID to check
     * @return result True if agent exists
     */
    function exists(uint256 agentId) external view returns (bool result) {
        return _ownerOf(agentId) != address(0);
    }

    /**
     * @notice Get owner of agent
     * @param agentId The agent ID
     * @return result The agent owner
     */
    function ownerOf(uint256 agentId) public view override(ERC721, IERC721) returns (address result) {
        result = _ownerOf(agentId);
        if (result == address(0)) revert InvalidAgentId();
    }

    // Override transfer functions to unset agent wallet
    function _update(
        address to,
        uint256 tokenId,
        address auth
    ) internal override returns (address) {
        address from = _ownerOf(tokenId);
        address result = super._update(to, tokenId, auth);
        
        // Unset agent wallet on transfer (but not minting/burning if we want to keep it? No, minting sets it in register(). Burning should clear it.)
        // Original code: if (from != address(0) && to != address(0)) -> unset
        // Minting: from == 0. Burning: to == 0.
        // Transfer: from != 0 && to != 0.
        
        if (from != address(0) && to != address(0)) {
            address previousWallet = _agentWallets[tokenId];
            delete _agentWallets[tokenId];
            emit AgentWalletUnset(tokenId, previousWallet);
        }
        
        return result;
    }

    /**
     * @notice Check if caller is authorized to manage agent
     * @param agentId The agent ID
     * @return authorized True if authorized
     */
    function _isAuthorized(uint256 agentId) internal view returns (bool authorized) {
        address owner = ownerOf(agentId);
        return (
            msg.sender == owner ||
            isApprovedForAll(owner, msg.sender) ||
            getApproved(agentId) == msg.sender
        );
    }

    /**
     * @notice Check if token exists
     * @param agentId The agent ID
     * @return result True if token exists
     */
    function _exists(uint256 agentId) internal view returns (bool result) {
        return _ownerOf(agentId) != address(0);
    }
}
