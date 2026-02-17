// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "@openzeppelin/contracts/token/ERC721/utils/ERC721Holder.sol";
import "../src/IdentityRegistry.sol";
import "../src/interfaces/IIdentityRegistry.sol";

contract IdentityRegistryTest is Test, ERC721Holder {
    IdentityRegistry public identityRegistry;
    address public owner;
    address public alice;
    address public bob;

    event Registered(uint256 indexed agentId, string tokenURI, address indexed owner);
    event MetadataSet(uint256 indexed agentId, string indexed indexedKey, string key, bytes value);
    event UriUpdated(uint256 indexed agentId, string newUri, address indexed updatedBy);
    event AgentWalletSet(uint256 indexed agentId, address indexed newWallet, address indexed updatedBy);
    event AgentWalletUnset(uint256 indexed agentId, address indexed previousWallet);

    function setUp() public {
        owner = address(this);
        alice = address(0x1);
        bob = address(0x2);

        identityRegistry = new IdentityRegistry();
    }

    function test_RegisterWithoutURI() public {
        vm.expectEmit(true, true, true, true, address(identityRegistry));
        emit Registered(0, "", owner);
        
        uint256 agentId = identityRegistry.register();
        
        assertEq(agentId, 0);
        assertEq(identityRegistry.ownerOf(agentId), owner);
        assertEq(identityRegistry.tokenURI(agentId), "");
    }

    function test_RegisterWithURI() public {
        string memory uri = "ipfs://QmTest";
        
        vm.expectEmit(true, true, true, true, address(identityRegistry));
        emit Registered(0, uri, owner);
        
        uint256 agentId = identityRegistry.register(uri);
        
        assertEq(agentId, 0);
        assertEq(identityRegistry.ownerOf(agentId), owner);
        assertEq(identityRegistry.tokenURI(agentId), uri);
    }

    function test_RegisterWithMetadata() public {
        string memory uri = "ipfs://QmTest";
        
        IIdentityRegistry.MetadataEntry[] memory metadata = new IIdentityRegistry.MetadataEntry[](2);
        metadata[0] = IIdentityRegistry.MetadataEntry({
            key: "name",
            value: abi.encodePacked("Test Agent")
        });
        metadata[1] = IIdentityRegistry.MetadataEntry({
            key: "version",
            value: abi.encodePacked("1.0.0")
        });
        
        uint256 agentId = identityRegistry.register(uri, metadata);
        
        assertEq(agentId, 0);
        assertEq(identityRegistry.ownerOf(agentId), owner);
        assertEq(identityRegistry.tokenURI(agentId), uri);
        assertEq(identityRegistry.getMetadata(agentId, "name"), abi.encodePacked("Test Agent"));
        assertEq(identityRegistry.getMetadata(agentId, "version"), abi.encodePacked("1.0.0"));
    }

    function test_SetMetadata() public {
        uint256 agentId = identityRegistry.register();
        
        vm.expectEmit(true, true, true, true, address(identityRegistry));
        emit MetadataSet(agentId, "test", "test", abi.encodePacked("value"));
        
        identityRegistry.setMetadata(agentId, "test", abi.encodePacked("value"));
        
        assertEq(identityRegistry.getMetadata(agentId, "test"), abi.encodePacked("value"));
    }

    function test_SetMetadataUnauthorized() public {
        uint256 agentId = identityRegistry.register();
        
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(IIdentityRegistry.NotAuthorized.selector));
        identityRegistry.setMetadata(agentId, "test", abi.encodePacked("value"));
    }

    function test_SetAgentUri() public {
        uint256 agentId = identityRegistry.register();
        string memory newUri = "ipfs://QmNew";
        
        vm.expectEmit(true, true, true, true, address(identityRegistry));
        emit UriUpdated(agentId, newUri, owner);
        
        identityRegistry.setAgentUri(agentId, newUri);
        
        assertEq(identityRegistry.tokenURI(agentId), newUri);
    }

    function test_SetAgentUriUnauthorized() public {
        uint256 agentId = identityRegistry.register();
        
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(IIdentityRegistry.NotAuthorized.selector));
        identityRegistry.setAgentUri(agentId, "ipfs://QmNew");
    }

    function test_SetAgentWallet() public {
        uint256 agentId = identityRegistry.register();
        address wallet = address(0x123);
        
        vm.expectEmit(true, true, true, true, address(identityRegistry));
        emit AgentWalletSet(agentId, wallet, owner);
        
        identityRegistry.setAgentWallet(agentId, wallet);
        
        assertEq(identityRegistry.getAgentWallet(agentId), wallet);
    }

    function test_SetAgentWalletUnauthorized() public {
        uint256 agentId = identityRegistry.register();
        
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(IIdentityRegistry.NotAuthorized.selector));
        identityRegistry.setAgentWallet(agentId, address(0x123));
    }

    function test_SetAgentWalletAlreadySet() public {
        uint256 agentId = identityRegistry.register();
        identityRegistry.setAgentWallet(agentId, address(0x123));
        
        vm.expectRevert(abi.encodeWithSelector(IIdentityRegistry.AgentWalletAlreadySet.selector));
        identityRegistry.setAgentWallet(agentId, address(0x456));
    }

    function test_UnsetAgentWallet() public {
        uint256 agentId = identityRegistry.register();
        address wallet = address(0x123);
        identityRegistry.setAgentWallet(agentId, wallet);
        
        vm.expectEmit(true, true, true, true, address(identityRegistry));
        emit AgentWalletUnset(agentId, wallet);
        
        identityRegistry.unsetAgentWallet(agentId);
        
        assertEq(identityRegistry.getAgentWallet(agentId), address(0));
    }

    function test_UnsetAgentWalletUnauthorized() public {
        uint256 agentId = identityRegistry.register();
        
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(IIdentityRegistry.NotAuthorized.selector));
        identityRegistry.unsetAgentWallet(agentId);
    }

    function test_TotalSupply() public {
        assertEq(identityRegistry.totalSupply(), 0);
        
        identityRegistry.register();
        assertEq(identityRegistry.totalSupply(), 1);
        
        identityRegistry.register();
        assertEq(identityRegistry.totalSupply(), 2);
    }

    function test_Exists() public {
        assertFalse(identityRegistry.exists(0));
        
        uint256 agentId = identityRegistry.register();
        assertTrue(identityRegistry.exists(agentId));
        assertFalse(identityRegistry.exists(999));
    }

    function test_GetMetadataInvalidAgent() public {
        vm.expectRevert(abi.encodeWithSelector(IIdentityRegistry.InvalidAgentId.selector));
        identityRegistry.getMetadata(0, "test");
    }

    function test_GetAgentWalletInvalidAgent() public {
        vm.expectRevert(abi.encodeWithSelector(IIdentityRegistry.InvalidAgentId.selector));
        identityRegistry.getAgentWallet(0);
    }

    function test_OwnerOfInvalidAgent() public {
        vm.expectRevert(abi.encodeWithSelector(IIdentityRegistry.InvalidAgentId.selector));
        identityRegistry.ownerOf(0);
    }

    function test_TransferUnsetsWallet() public {
        uint256 agentId = identityRegistry.register();
        address wallet = address(0x123);
        identityRegistry.setAgentWallet(agentId, wallet);
        
        vm.expectEmit(true, true, true, true, address(identityRegistry));
        emit AgentWalletUnset(agentId, wallet);
        
        // Transfer to alice
        identityRegistry.transferFrom(owner, alice, agentId);
        
        assertEq(identityRegistry.ownerOf(agentId), alice);
        assertEq(identityRegistry.getAgentWallet(agentId), address(0));
    }

    function test_ApprovedCanSetMetadata() public {
        uint256 agentId = identityRegistry.register();
        
        // Approve alice
        identityRegistry.approve(alice, agentId);
        
        vm.prank(alice);
        identityRegistry.setMetadata(agentId, "test", abi.encodePacked("value"));
        
        assertEq(identityRegistry.getMetadata(agentId, "test"), abi.encodePacked("value"));
    }

    function test_OperatorCanSetMetadata() public {
        uint256 agentId = identityRegistry.register();
        
        // Set alice as operator
        identityRegistry.setApprovalForAll(alice, true);
        
        vm.prank(alice);
        identityRegistry.setMetadata(agentId, "test", abi.encodePacked("value"));
        
        assertEq(identityRegistry.getMetadata(agentId, "test"), abi.encodePacked("value"));
    }

    function testFuzz_Register(uint8 count) public {
        vm.assume(count > 0 && count <= 10);
        
        for (uint256 i = 0; i < count; i++) {
            uint256 agentId = identityRegistry.register();
            assertEq(agentId, i);
            assertEq(identityRegistry.ownerOf(agentId), owner);
        }
        
        assertEq(identityRegistry.totalSupply(), count);
    }

    function testFuzz_MetadataKeyValue(string memory key, bytes memory value) public {
        vm.assume(bytes(key).length > 0);
        uint256 agentId = identityRegistry.register();
        
        identityRegistry.setMetadata(agentId, key, value);
        
        assertEq(identityRegistry.getMetadata(agentId, key), value);
    }
}
