// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "@openzeppelin/contracts/token/ERC721/utils/ERC721Holder.sol";
import "../src/IdentityRegistry.sol";
import "../src/TEERegistry.sol";
import "../src/mocks/MockTEEVerifier.sol";
import "../src/interfaces/ITEERegistry.sol";
import "../src/interfaces/IIdentityRegistry.sol";

contract TEERegistryTest is Test, ERC721Holder {
    IdentityRegistry public identityRegistry;
    TEERegistry public teeRegistry;
    MockTEEVerifier public mockVerifier;
    address public owner;
    address public alice;
    address public bob;
    uint256 public agentId;

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

    function setUp() public {
        owner = address(this);
        alice = address(0x1);
        bob = address(0x2);

        identityRegistry = new IdentityRegistry();
        teeRegistry = new TEERegistry(address(identityRegistry));
        mockVerifier = new MockTEEVerifier();
        
        // Register a test agent
        agentId = identityRegistry.register();
    }

    function test_AddVerifier() public {
        address verifier = address(mockVerifier);
        bytes32 teeArch = keccak256("TDX");
        
        vm.expectEmit(true, true, true, true, address(teeRegistry));
        emit VerifierAdded(verifier, teeArch);
        
        teeRegistry.addVerifier(verifier, teeArch);
        
        assertTrue(teeRegistry.isVerifier(verifier));
        assertEq(teeRegistry.verifiers(verifier).teeArch, teeArch);
    }

    function test_AddVerifierUnauthorized() public {
        vm.prank(alice);
        vm.expectRevert();
        teeRegistry.addVerifier(address(mockVerifier), keccak256("TDX"));
    }

    function test_AddVerifierInvalidAddress() public {
        vm.expectRevert(abi.encodeWithSelector(ITEERegistry.InvalidVerifier.selector));
        teeRegistry.addVerifier(address(0), keccak256("TDX"));
    }

    function test_RemoveVerifier() public {
        address verifier = address(mockVerifier);
        bytes32 teeArch = keccak256("TDX");
        
        teeRegistry.addVerifier(verifier, teeArch);
        
        vm.expectEmit(true, true, true, true, address(teeRegistry));
        emit VerifierRemoved(verifier);
        
        teeRegistry.removeVerifier(verifier);
        
        assertFalse(teeRegistry.isVerifier(verifier));
    }

    function test_RemoveVerifierUnauthorized() public {
        address verifier = address(mockVerifier);
        teeRegistry.addVerifier(verifier, keccak256("TDX"));
        
        vm.prank(alice);
        vm.expectRevert();
        teeRegistry.removeVerifier(verifier);
    }

    function test_AddKey() public {
        address verifier = address(mockVerifier);
        bytes32 teeArch = keccak256("TDX");
        bytes32 codeMeasurement = keccak256("code");
        address pubkey = address(0x456);
        string memory codeConfigUri = "ipfs://QmTest";
        bytes memory proof = abi.encodePacked("proof");
        
        // Add verifier first
        teeRegistry.addVerifier(verifier, teeArch);
        
        vm.expectEmit(true, true, true, true, address(teeRegistry));
        emit KeyAdded(agentId, teeArch, codeMeasurement, pubkey, codeConfigUri, verifier);
        
        teeRegistry.addKey(
            agentId,
            teeArch,
            codeMeasurement,
            pubkey,
            codeConfigUri,
            verifier,
            proof
        );
        
        assertTrue(teeRegistry.hasKey(agentId, pubkey));
        assertEq(teeRegistry.getKeyCount(agentId), 1);
        assertEq(teeRegistry.getKeyAtIndex(agentId, 0), pubkey);
        
        ITEERegistry.Key memory key = teeRegistry.getKey(agentId, pubkey);
        assertEq(key.teeArch, teeArch);
        assertEq(key.codeMeasurement, codeMeasurement);
        assertEq(key.codeConfigUri, codeConfigUri);
        assertEq(key.verifier, verifier);
    }

    function test_AddKeyInvalidAgent() public {
        address verifier = address(mockVerifier);
        teeRegistry.addVerifier(verifier, keccak256("TDX"));
        
        vm.expectRevert(abi.encodeWithSelector(IIdentityRegistry.InvalidAgentId.selector));
        teeRegistry.addKey(
            999,
            keccak256("TDX"),
            keccak256("code"),
            address(0x456),
            "ipfs://QmTest",
            verifier,
            abi.encodePacked("proof")
        );
    }

    function test_AddKeyUnauthorized() public {
        address verifier = address(mockVerifier);
        teeRegistry.addVerifier(verifier, keccak256("TDX"));
        
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(ITEERegistry.NotAuthorized.selector));
        teeRegistry.addKey(
            agentId,
            keccak256("TDX"),
            keccak256("code"),
            address(0x456),
            "ipfs://QmTest",
            verifier,
            abi.encodePacked("proof")
        );
    }

    function test_AddKeyVerifierNotWhitelisted() public {
        vm.expectRevert(abi.encodeWithSelector(ITEERegistry.VerifierNotWhitelisted.selector));
        teeRegistry.addKey(
            agentId,
            keccak256("TDX"),
            keccak256("code"),
            address(0x456),
            "ipfs://QmTest",
            address(mockVerifier),
            abi.encodePacked("proof")
        );
    }

    function test_AddKeyAlreadyExists() public {
        address verifier = address(mockVerifier);
        address pubkey = address(0x456);
        
        teeRegistry.addVerifier(verifier, keccak256("TDX"));
        teeRegistry.addKey(
            agentId,
            keccak256("TDX"),
            keccak256("code"),
            pubkey,
            "ipfs://QmTest",
            verifier,
            abi.encodePacked("proof")
        );
        
        vm.expectRevert(abi.encodeWithSelector(ITEERegistry.KeyAlreadyExists.selector));
        teeRegistry.addKey(
            agentId,
            keccak256("TDX"),
            keccak256("code2"),
            pubkey,
            "ipfs://QmTest2",
            verifier,
            abi.encodePacked("proof2")
        );
    }

    function test_RemoveKey() public {
        address verifier = address(mockVerifier);
        address pubkey = address(0x456);
        
        teeRegistry.addVerifier(verifier, keccak256("TDX"));
        teeRegistry.addKey(
            agentId,
            keccak256("TDX"),
            keccak256("code"),
            pubkey,
            "ipfs://QmTest",
            verifier,
            abi.encodePacked("proof")
        );
        
        vm.expectEmit(true, true, true, true, address(teeRegistry));
        emit KeyRemoved(agentId, pubkey);
        
        teeRegistry.removeKey(agentId, pubkey);
        
        assertFalse(teeRegistry.hasKey(agentId, pubkey));
        assertEq(teeRegistry.getKeyCount(agentId), 0);
    }

    function test_RemoveKeyUnauthorized() public {
        address verifier = address(mockVerifier);
        address pubkey = address(0x456);
        
        teeRegistry.addVerifier(verifier, keccak256("TDX"));
        teeRegistry.addKey(
            agentId,
            keccak256("TDX"),
            keccak256("code"),
            pubkey,
            "ipfs://QmTest",
            verifier,
            abi.encodePacked("proof")
        );
        
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(ITEERegistry.NotAuthorized.selector));
        teeRegistry.removeKey(agentId, pubkey);
    }

    function test_GetKeyNotFound() public {
        vm.expectRevert(abi.encodeWithSelector(ITEERegistry.KeyNotFound.selector));
        teeRegistry.getKey(agentId, address(0x456));
    }

    function test_GetAgentKeys() public {
        address verifier = address(mockVerifier);
        address[] memory pubkeys = new address[](3);
        pubkeys[0] = address(0x456);
        pubkeys[1] = address(0x789);
        pubkeys[2] = address(0xABC);
        
        teeRegistry.addVerifier(verifier, keccak256("TDX"));
        
        for (uint256 i = 0; i < 3; i++) {
            teeRegistry.addKey(
                agentId,
                keccak256("TDX"),
                keccak256(abi.encodePacked("code", i)),
                pubkeys[i],
                "ipfs://QmTest",
                verifier,
                abi.encodePacked("proof")
            );
        }
        
        address[] memory keys = teeRegistry.getAgentKeys(agentId);
        assertEq(keys.length, 3);
        
        for (uint256 i = 0; i < 3; i++) {
            assertTrue(keys[i] == pubkeys[0] || keys[i] == pubkeys[1] || keys[i] == pubkeys[2]);
        }
    }

    function test_GetKeyRegistrationTime() public {
        address verifier = address(mockVerifier);
        address pubkey = address(0x456);
        
        teeRegistry.addVerifier(verifier, keccak256("TDX"));
        
        uint256 timestampBefore = block.timestamp;
        teeRegistry.addKey(
            agentId,
            keccak256("TDX"),
            keccak256("code"),
            pubkey,
            "ipfs://QmTest",
            verifier,
            abi.encodePacked("proof")
        );
        uint256 timestampAfter = block.timestamp;
        
        uint256 registrationTime = teeRegistry.getKeyRegistrationTime(pubkey);
        assertTrue(registrationTime >= timestampBefore && registrationTime <= timestampAfter);
    }

    function test_ApprovedCanAddKey() public {
        address verifier = address(mockVerifier);
        address pubkey = address(0x456);
        
        // Approve alice
        identityRegistry.approve(alice, agentId);
        
        teeRegistry.addVerifier(verifier, keccak256("TDX"));
        
        vm.prank(alice);
        teeRegistry.addKey(
            agentId,
            keccak256("TDX"),
            keccak256("code"),
            pubkey,
            "ipfs://QmTest",
            verifier,
            abi.encodePacked("proof")
        );
        
        assertTrue(teeRegistry.hasKey(agentId, pubkey));
    }

    function test_OperatorCanAddKey() public {
        address verifier = address(mockVerifier);
        address pubkey = address(0x456);
        
        // Set alice as operator
        identityRegistry.setApprovalForAll(alice, true);
        
        teeRegistry.addVerifier(verifier, keccak256("TDX"));
        
        vm.prank(alice);
        teeRegistry.addKey(
            agentId,
            keccak256("TDX"),
            keccak256("code"),
            pubkey,
            "ipfs://QmTest",
            verifier,
            abi.encodePacked("proof")
        );
        
        assertTrue(teeRegistry.hasKey(agentId, pubkey));
    }

    function testFuzz_AddMultipleKeys(uint8 count) public {
        vm.assume(count > 0 && count <= 10);
        
        address verifier = address(mockVerifier);
        teeRegistry.addVerifier(verifier, keccak256("TDX"));
        
        for (uint256 i = 0; i < count; i++) {
            address pubkey = address(uint160(0x456 + i));
            teeRegistry.addKey(
                agentId,
                keccak256("TDX"),
                keccak256(abi.encodePacked("code", i)),
                pubkey,
                "ipfs://QmTest",
                verifier,
                abi.encodePacked("proof")
            );
        }
        
        assertEq(teeRegistry.getKeyCount(agentId), count);
    }
}
