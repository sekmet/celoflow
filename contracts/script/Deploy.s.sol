// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/IdentityRegistry.sol";
import "../src/ReputationRegistry.sol";
import "../src/TEERegistry.sol";
import "../src/mocks/MockTEEVerifier.sol";
import "../src/interfaces/IIdentityRegistry.sol";

/**
 * @title RegistrationHelperSepolia
 * @notice Helper contract to register agents (implements ERC721Received)
 * @dev Needed because register() mints an NFT — EOAs can't receive via _safeMint
 */
contract RegistrationHelperSepolia {
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
 * @title DeployScript
 * @notice Foundry script for deploying ERC-8004 Remittance Agent infrastructure
 * @dev Deploys to Celo Sepolia Testnet (chain ID 44787)
 *
 * Usage:
 *   # Load env and deploy
 *   source .env
 *   forge script script/Deploy.s.sol:DeployScript \
 *       --rpc-url $CELO_SEPOLIA_RPC_URL \
 *       --broadcast --verify -vvvv
 *
 * Note: DeployAnvil.s.sol is the script for local Anvil dev — this does NOT touch it.
 */
contract DeployScript is Script {
    // Celo Sepolia Testnet configuration
    uint256 private constant CELO_SEPOLIA_CHAIN_ID = 11142220;

    bytes32 private constant TDX_ARCH = keccak256("TDX");

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
        // Get deployer private key from environment
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);

        vm.startBroadcast(deployerPrivateKey);

        console.log(unicode"🚀 Starting ERC-8004 Remittance Agent deployment...");
        console.log("   Chain: Celo Sepolia Testnet (", block.chainid, ")");
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

        // 4. Deploy MockTEEVerifier (used for testing on testnet — no real DCAP verifier on Celo Sepolia)
        console.log(unicode"\n🔐 4. Deploying MockTEEVerifier for testnet...");
        MockTEEVerifier mockVerifier = new MockTEEVerifier();
        address verifierAddress = address(mockVerifier);
        console.log(unicode"   ✅ MockTEEVerifier deployed:", verifierAddress);

        // 5. Add MockTEEVerifier to TEERegistry
        console.log(unicode"\n🔐 5. Adding MockTEEVerifier to TEERegistry...");
        teeRegistry.addVerifier(verifierAddress, TDX_ARCH);
        console.log(unicode"   ✅ Mock verifier whitelisted:", verifierAddress);

        // 6. Register a sample remittance agent
        console.log(unicode"\n🤖 6. Registering Remittance Agent...");

        // Deploy RegistrationHelper (needed because register() mints NFT via _safeMint)
        RegistrationHelperSepolia helper = new RegistrationHelperSepolia();

        // The deployer is also the agent owner on testnet
        uint256 agentId = _registerSampleAgent(identityRegistry, helper, deployer);
        console.log(unicode"   ✅ Agent registered with ID:", agentId);

        // 7. Set up sample TEE key for the agent
        console.log(unicode"\n🔑 7. Setting up sample TEE key...");
        _setupSampleTEEKey(teeRegistry, identityRegistry, agentId, verifierAddress, deployer);
        console.log(unicode"   ✅ Sample TEE key configured");

        vm.stopBroadcast();

        // 8. Save deployment information
        console.log(unicode"\n💾 8. Saving deployment information...");

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

        console.log(unicode"\n🎉 Celo Sepolia deployment completed successfully!");
        console.log(unicode"📁 Check .env.deployed for contract addresses");
        console.log(unicode"📁 Check deployment.json for programmatic access");
        console.log(unicode"🔗 Verify contracts on Celo Explorer: https://sepolia.celoscan.io");
    }

    /**
     * @notice Register a sample remittance agent via RegistrationHelper
     * @param identityRegistry The IdentityRegistry contract
     * @param helper The RegistrationHelper contract
     * @param agentOwner The address that will own the agent NFT
     * @return agentId The registered agent ID
     */
    function _registerSampleAgent(
        IdentityRegistry identityRegistry,
        RegistrationHelperSepolia helper,
        address agentOwner
    ) internal returns (uint256 agentId) {
        // Prepare agent metadata
        string memory tokenUri = "ipfs://QmCeloFlowRemittanceAgentMetadata";

        // Prepare metadata entries
        IIdentityRegistry.MetadataEntry[] memory metadata = new IIdentityRegistry.MetadataEntry[](3);

        metadata[0] = IIdentityRegistry.MetadataEntry({
            key: "name",
            value: abi.encodePacked("CeloFlow Remittance Agent")
        });

        metadata[1] = IIdentityRegistry.MetadataEntry({
            key: "description",
            value: abi.encodePacked("AI-powered cross-border remittances on Celo (Sepolia Testnet)")
        });

        metadata[2] = IIdentityRegistry.MetadataEntry({
            key: "version",
            value: abi.encodePacked("1.0.0-sepolia")
        });

        // Register using helper (mints to helper, transfers to agentOwner)
        agentId = helper.doRegister(identityRegistry, tokenUri, metadata, agentOwner);

        return agentId;
    }

    /**
     * @notice Set up a sample TEE key for the agent
     * @param teeRegistry The TEERegistry contract
     * @param identityRegistry The IdentityRegistry contract
     * @param agentId The agent ID
     * @param verifierAddress The mock verifier address
     * @param agentOwner The agent owner address
     */
    function _setupSampleTEEKey(
        TEERegistry teeRegistry,
        IdentityRegistry identityRegistry,
        uint256 agentId,
        address verifierAddress,
        address agentOwner
    ) internal {
        // Set agent wallet
        address agentWallet = agentOwner;  // On testnet, owner = wallet
        identityRegistry.setAgentWallet(agentId, agentWallet);

        // Sample TEE key data
        bytes32 teeArch = TDX_ARCH;
        bytes32 codeMeasurement = keccak256("celoflow-remittance-agent-v1");
        address pubkey = agentOwner;  // On testnet, use deployer as pubkey
        string memory codeConfigUri = "ipfs://QmCeloFlowCodeConfig";

        // Mock attestation proof (in production, this would be a real TEE attestation)
        bytes memory proof = abi.encodePacked(
            "celoflow-sepolia-attestation-proof"
        );

        // Add the TEE key
        teeRegistry.addKey(
            agentId,
            teeArch,
            codeMeasurement,
            pubkey,
            codeConfigUri,
            verifierAddress,
            proof
        );
    }

    /**
     * @notice Save deployment information to .env.deployed and deployment.json
     * @param info Deployment info struct
     */
    function _saveDeploymentInfo(DeploymentInfo memory info) internal {
        _saveEnvFile(info);
        _saveJsonFile(info);
    }

    function _saveEnvFile(DeploymentInfo memory info) internal {
        string memory content = string.concat(
            "# ERC-8004 Remittance Agent Deployment (Celo Sepolia)\n",
            "# Chain ID: 11142220\n",
            "# RPC: https://celo-sepolia.g.alchemy.com/v2/E1tpzIwNYKbEADvBUW4fnAq13UCobt_3\n",
            "# Generated: ", vm.toString(info.timestamp), "\n\n"
        );
        content = string.concat(content, "IDENTITY_REGISTRY=", vm.toString(info.identityRegistry), "\n");
        content = string.concat(content, "REPUTATION_REGISTRY=", vm.toString(info.reputationRegistry), "\n");
        content = string.concat(content, "TEE_REGISTRY=", vm.toString(info.teeRegistry), "\n");
        content = string.concat(content, "MOCK_TEE_VERIFIER=", vm.toString(info.verifierAddress), "\n");
        content = string.concat(content, "DEPLOYER=", vm.toString(info.deployer), "\n");
        content = string.concat(content, "AGENT_ID=", vm.toString(info.agentId), "\n");
        content = string.concat(content, "CHAIN_ID=", vm.toString(CELO_SEPOLIA_CHAIN_ID), "\n");

        vm.writeFile(".env.deployed", content);
        console.log(unicode"   📄 .env.deployed created");
    }

    function _saveJsonFile(DeploymentInfo memory info) internal {
        string memory json = string.concat(
            "{\n",
            '  "network": "celo-sepolia",\n',
            '  "chainId": ', vm.toString(CELO_SEPOLIA_CHAIN_ID), ',\n',
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

        vm.writeFile("deployment.json", json);
        console.log(unicode"   📄 deployment.json created");
    }
}
