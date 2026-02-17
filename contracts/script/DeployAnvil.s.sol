// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/IdentityRegistry.sol";
import "../src/ReputationRegistry.sol";
import "../src/TEERegistry.sol";
import "../src/mocks/MockTEEVerifier.sol";
import "../src/interfaces/IIdentityRegistry.sol";

contract RegistrationHelper {
    function doRegister(
        IdentityRegistry identityRegistry,
        string memory tokenUri,
        IIdentityRegistry.MetadataEntry[] memory metadata,
        address finalOwner
    ) external returns (uint256) {
        // Register (mints to this contract)
        uint256 agentId = identityRegistry.register(tokenUri, metadata);
        
        // Transfer to final owner using unsafe transfer to avoid onERC721Received check on EOA
        identityRegistry.transferFrom(address(this), finalOwner, agentId);
        
        return agentId;
    }

    function onERC721Received(
        address,
        address,
        uint256,
        bytes calldata
    ) external pure returns (bytes4) {
        return this.onERC721Received.selector;
    }
}

/**
 * @title DeployAnvilScript
 * @notice Foundry script for deploying ERC-8004 Remittance Agent infrastructure to local Anvil
 * @dev Deploys to local Anvil forked from Celo Sepolia
 */
contract DeployAnvilScript is Script {
    // Celo Sepolia Testnet configuration (for reference in fork)
    uint256 private constant CELO_SEPOLIA_CHAIN_ID = 44787;
    
    bytes32 private constant TDX_ARCH = keccak256("TDX");

    // Anvil Default Private Key #0 (Account 0)
    uint256 private constant ANVIL_PRIVATE_KEY = 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80;
    
    // Anvil Private Key #1 (Account 1) - used for Agent Owner to avoid conflicts
    uint256 private constant ANVIL_PRIVATE_KEY_2 = 0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d;

    struct DeploymentInfo {
        address identityRegistry;
        address reputationRegistry;
        address teeRegistry;
        address verifierAddress;
        address deployer;
        uint256 agentId;
        uint256 timestamp;
    }

    function run() external {
        // Use Anvil default private key
        uint256 deployerPrivateKey = ANVIL_PRIVATE_KEY;
        address deployer = vm.addr(deployerPrivateKey);
        
        vm.startBroadcast(deployerPrivateKey);
        
        console.log(unicode"🚀 Starting ERC-8004 Remittance Agent deployment to Anvil...");
        console.log("   Chain ID:", block.chainid);
        console.log("   Deployer: ", deployer);
        
        // 1. Deploy IdentityRegistry
        console.log(unicode"\n📋 1. Deploying IdentityRegistry...");
        IdentityRegistry identityRegistry = new IdentityRegistry();
        console.log(unicode"   ✅ IdentityRegistry deployed:", address(identityRegistry));
        
        // 2. Deploy ReputationRegistry
        console.log(unicode"\n⭐ 2. Deploying ReputationRegistry...");
        ReputationRegistry reputationRegistry = new ReputationRegistry(address(identityRegistry));
        console.log(unicode"   ✅ ReputationRegistry deployed:", address(reputationRegistry));
        
        // 3. Deploy TEERegistry
        console.log(unicode"\n🔒 3. Deploying TEERegistry...");
        TEERegistry teeRegistry = new TEERegistry(address(identityRegistry));
        console.log(unicode"   ✅ TEERegistry deployed:", address(teeRegistry));

        // 4. Deploy MockTEEVerifier for local testing
        console.log(unicode"\n🔐 4. Deploying MockTEEVerifier...");
        MockTEEVerifier mockVerifier = new MockTEEVerifier();
        address verifierAddress = address(mockVerifier);
        console.log(unicode"   ✅ MockTEEVerifier deployed:", verifierAddress);
        
        // 5. Add MockTEEVerifier to TEERegistry
        console.log(unicode"\n🔐 5. Adding MockTEEVerifier to TEERegistry...");
        teeRegistry.addVerifier(verifierAddress, TDX_ARCH);
        console.log(unicode"   ✅ Mock verifier whitelisted:", verifierAddress);
        
        // 6. Register a sample remittance agent
        console.log(unicode"\n🤖 6. Registering sample Remittance Agent...");
        
        // Deploy Helper
        RegistrationHelper helper = new RegistrationHelper();
        
        // Use Account 1 as agent owner
        address agentOwner = vm.addr(ANVIL_PRIVATE_KEY_2);
        
        uint256 agentId = _registerSampleAgent(identityRegistry, helper, agentOwner);
        console.log(unicode"   ✅ Sample agent registered with ID:", agentId);
        
        // 7. Set up sample TEE key for the agent
        console.log(unicode"\n🔑 7. Setting up sample TEE key...");
        _setupSampleTEEKey(teeRegistry, identityRegistry, agentId, verifierAddress, agentOwner);
        console.log(unicode"   ✅ Sample TEE key configured");
        
        vm.stopBroadcast();
        
        // 8. Save deployment information
        console.log(unicode"\n💾 8. Saving Anvil deployment information...");
        
        DeploymentInfo memory info = DeploymentInfo({
            identityRegistry: address(identityRegistry),
            reputationRegistry: address(reputationRegistry),
            teeRegistry: address(teeRegistry),
            verifierAddress: verifierAddress,
            deployer: deployer,
            agentId: agentId,
            timestamp: block.timestamp
        });
        
        _saveDeploymentInfo(info);
        
        console.log(unicode"\n🎉 Anvil Deployment completed successfully!");
        console.log(unicode"📁 Check .env.anvil for contract addresses");
    }

    /**
     * @notice Register a sample remittance agent
     * @param identityRegistry The IdentityRegistry contract
     * @return agentId The registered agent ID
     */
    function _registerSampleAgent(
        IdentityRegistry identityRegistry, 
        RegistrationHelper helper,
        address agentOwner
    ) internal returns (uint256 agentId) {
        // Prepare agent metadata
        string memory tokenUri = "ipfs://QmSampleAgentMetadataHash";
        
        // Prepare metadata entries
        IIdentityRegistry.MetadataEntry[] memory metadata = new IIdentityRegistry.MetadataEntry[](3);
        
        metadata[0] = IIdentityRegistry.MetadataEntry({
            key: "name",
            value: abi.encodePacked("Remittance Intent Agent (Local)")
        });
        
        metadata[1] = IIdentityRegistry.MetadataEntry({
            key: "description",
            value: abi.encodePacked("AI-powered cross-border remittances (Anvil Local Test)")
        });
        
        metadata[2] = IIdentityRegistry.MetadataEntry({
            key: "version",
            value: abi.encodePacked("1.0.0-local")
        });
        
        // Register using helper
        agentId = helper.doRegister(identityRegistry, tokenUri, metadata, agentOwner);
        
        return agentId;
    }

    /**
     * @notice Set up a sample TEE key for the agent
     * @param teeRegistry The TEERegistry contract
     * @param agentId The agent ID
     * @param verifierAddress The mock verifier address
     */
    function _setupSampleTEEKey(
        TEERegistry teeRegistry, 
        IdentityRegistry identityRegistry,
        uint256 agentId, 
        address verifierAddress,
        address agentOwner
    ) internal {
        // Switch broadcast to Agent Owner (Account 1) to set wallet and keys
        vm.stopBroadcast();
        vm.startBroadcast(ANVIL_PRIVATE_KEY_2);

        // Set agent wallet (as new owner)
        address agentWallet = address(0x1111111111111111111111111111111111111111);
        identityRegistry.setAgentWallet(agentId, agentWallet);

        // Sample TEE key data
        bytes32 teeArch = TDX_ARCH;
        bytes32 codeMeasurement = keccak256("sample-code-measurement-local");
        address pubkey = address(0x2222222222222222222222222222222222222222);
        string memory codeConfigUri = "ipfs://QmSampleCodeConfigHash";
        
        // Mock attestation proof
        bytes memory proof = abi.encodePacked(
            "sample-local-attestation-proof"
        );

        teeRegistry.addKey(
            agentId,
            teeArch,
            codeMeasurement,
            pubkey,
            codeConfigUri,
            verifierAddress,
            proof
        );

        vm.stopBroadcast();
        vm.startBroadcast(ANVIL_PRIVATE_KEY);
    }

    /**
     * @notice Save deployment information to file (Anvil specific)
     * @param info Deployment info struct
     */
    function _saveDeploymentInfo(DeploymentInfo memory info) internal {
        _saveEnvFile(info);
        _saveJsonFile(info);
    }

    function _saveEnvFile(DeploymentInfo memory info) internal {
        string memory content = string.concat(
            "# ERC-8004 Remittance Agent Deployment (Anvil Local)\n",
            "# Celo Sepolia Fork\n",
            "# Generated: ", vm.toString(info.timestamp), "\n\n"
        );
        content = string.concat(content, "IDENTITY_REGISTRY=", vm.toString(info.identityRegistry), "\n");
        content = string.concat(content, "REPUTATION_REGISTRY=", vm.toString(info.reputationRegistry), "\n");
        content = string.concat(content, "TEE_REGISTRY=", vm.toString(info.teeRegistry), "\n");
        content = string.concat(content, "MOCK_TEE_VERIFIER=", vm.toString(info.verifierAddress), "\n");
        content = string.concat(content, "DEPLOYER=", vm.toString(info.deployer), "\n");
        content = string.concat(content, "AGENT_ID=", vm.toString(info.agentId), "\n");
        content = string.concat(content, "CHAIN_ID=", vm.toString(block.chainid), "\n");
        
        vm.writeFile(".env.anvil", content);
        console.log(unicode"   📄 .env.anvil created");
    }

    function _saveJsonFile(DeploymentInfo memory info) internal {
        string memory json = string.concat(
            "{\n",
            '  "network": "anvil-fork",\n',
            '  "chainId": ', vm.toString(block.chainid), ',\n',
            '  "timestamp": ', vm.toString(info.timestamp), ',\n'
        );
        
        json = string.concat(json, '  "deployer": "', vm.toString(info.deployer), '",\n');
        json = string.concat(json, '  "agentId": ', vm.toString(info.agentId), ',\n');
        
        string memory contracts = string.concat(
            '  "contracts": {\n',
            '    "IdentityRegistry": "', vm.toString(info.identityRegistry), '",\n',
            '    "ReputationRegistry": "', vm.toString(info.reputationRegistry), '",\n',
            '    "TEERegistry": "', vm.toString(info.teeRegistry), '"\n',
            '  },\n'
        );
        
        json = string.concat(json, contracts);
        json = string.concat(json, '  "verifiers": {\n    "MockTEEVerifier": "', vm.toString(info.verifierAddress), '"\n  }\n}\n');
        
        vm.writeFile("deployment-anvil.json", json);
        console.log(unicode"   📄 deployment-anvil.json created");
    }
}
