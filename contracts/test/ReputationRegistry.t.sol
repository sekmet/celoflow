// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "@openzeppelin/contracts/token/ERC721/utils/ERC721Holder.sol";
import "../src/IdentityRegistry.sol";
import "../src/ReputationRegistry.sol";
import "../src/interfaces/IReputationRegistry.sol";
import "../src/interfaces/IIdentityRegistry.sol";

contract ReputationRegistryTest is Test, ERC721Holder {
    IdentityRegistry public identityRegistry;
    ReputationRegistry public reputationRegistry;
    address public owner;
    address public alice;
    address public bob;
    uint256 public agentId;

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

    function setUp() public {
        owner = address(this);
        alice = address(0x1);
        bob = address(0x2);

        identityRegistry = new IdentityRegistry();
        reputationRegistry = new ReputationRegistry(address(identityRegistry));
        
        // Register a test agent
        agentId = identityRegistry.register();
    }

    function test_GiveFeedback() public {
        int128 value = 85;
        uint8 decimals = 0;
        string memory tag1 = "performance";
        string memory tag2 = "reliability";
        
        vm.expectEmit(true, true, false, true, address(reputationRegistry));
        emit FeedbackGiven(agentId, alice, value, decimals, tag1, tag2);
        
        vm.prank(alice);
        reputationRegistry.giveFeedback(
            agentId,
            value,
            decimals,
            tag1,
            tag2,
            "endpoint",
            "ipfs://QmTest",
            keccak256("test")
        );
        
        (int128 readValue, uint8 readDecimals, string memory readTag1, string memory readTag2, bool isRevoked) = 
            reputationRegistry.readFeedback(agentId, alice, 0);
        
        assertEq(readValue, value);
        assertEq(readDecimals, decimals);
        assertEq(readTag1, tag1);
        assertEq(readTag2, tag2);
        assertFalse(isRevoked);
    }

    function test_GiveFeedbackInvalidAgent() public {
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(IIdentityRegistry.InvalidAgentId.selector));
        reputationRegistry.giveFeedback(
            999,
            85,
            0,
            "performance",
            "reliability",
            "endpoint",
            "ipfs://QmTest",
            keccak256("test")
        );
    }

    function test_GiveFeedbackSelfFeedback() public {
        vm.prank(owner);
        vm.expectRevert(abi.encodeWithSelector(IReputationRegistry.SelfFeedback.selector));
        reputationRegistry.giveFeedback(
            agentId,
            85,
            0,
            "performance",
            "reliability",
            "endpoint",
            "ipfs://QmTest",
            keccak256("test")
        );
    }

    function test_GiveFeedbackInvalidValue() public {
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(IReputationRegistry.InvalidValue.selector));
        reputationRegistry.giveFeedback(
            agentId,
            0,
            0,
            "performance",
            "reliability",
            "endpoint",
            "ipfs://QmTest",
            keccak256("test")
        );
    }

    function test_GiveFeedbackInvalidDecimals() public {
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(IReputationRegistry.InvalidDecimals.selector));
        reputationRegistry.giveFeedback(
            agentId,
            85,
            19, // > 18
            "performance",
            "reliability",
            "endpoint",
            "ipfs://QmTest",
            keccak256("test")
        );
    }

    function test_GetSummary() public {
        // Give multiple feedback entries
        vm.prank(alice);
        reputationRegistry.giveFeedback(
            agentId,
            80,
            0,
            "performance",
            "reliability",
            "endpoint",
            "ipfs://QmTest1",
            keccak256("test1")
        );
        
        vm.prank(bob);
        reputationRegistry.giveFeedback(
            agentId,
            90,
            0,
            "performance",
            "reliability",
            "endpoint",
            "ipfs://QmTest2",
            keccak256("test2")
        );
        
        (uint64 count, int128 summaryValue, uint8 summaryDecimals) = 
            reputationRegistry.getSummary(agentId, new address[](0), "", "");
        
        assertEq(count, 2);
        assertEq(summaryValue, 85); // (80 + 90) / 2
        assertEq(summaryDecimals, 0);
    }

    function test_GetSummaryWithTagFilter() public {
        // Give feedback with different tags
        vm.prank(alice);
        reputationRegistry.giveFeedback(
            agentId,
            80,
            0,
            "performance",
            "reliability",
            "endpoint",
            "ipfs://QmTest1",
            keccak256("test1")
        );
        
        vm.prank(bob);
        reputationRegistry.giveFeedback(
            agentId,
            90,
            0,
            "security",
            "reliability",
            "endpoint",
            "ipfs://QmTest2",
            keccak256("test2")
        );
        
        // Filter by tag1 = "performance"
        (uint64 count, int128 summaryValue, uint8 summaryDecimals) = 
            reputationRegistry.getSummary(agentId, new address[](0), "performance", "");
        
        assertEq(count, 1);
        assertEq(summaryValue, 80);
        assertEq(summaryDecimals, 0);
    }

    function test_GetSummaryWithClientFilter() public {
        // Give feedback from multiple clients
        vm.prank(alice);
        reputationRegistry.giveFeedback(
            agentId,
            80,
            0,
            "performance",
            "reliability",
            "endpoint",
            "ipfs://QmTest1",
            keccak256("test1")
        );
        
        vm.prank(bob);
        reputationRegistry.giveFeedback(
            agentId,
            90,
            0,
            "performance",
            "reliability",
            "endpoint",
            "ipfs://QmTest2",
            keccak256("test2")
        );
        
        address[] memory clients = new address[](1);
        clients[0] = alice;
        
        (uint64 count, int128 summaryValue, uint8 summaryDecimals) = 
            reputationRegistry.getSummary(agentId, clients, "", "");
        
        assertEq(count, 1);
        assertEq(summaryValue, 80);
        assertEq(summaryDecimals, 0);
    }

    function test_GetClients() public {
        vm.prank(alice);
        reputationRegistry.giveFeedback(
            agentId,
            80,
            0,
            "performance",
            "reliability",
            "endpoint",
            "ipfs://QmTest1",
            keccak256("test1")
        );
        
        vm.prank(bob);
        reputationRegistry.giveFeedback(
            agentId,
            90,
            0,
            "performance",
            "reliability",
            "endpoint",
            "ipfs://QmTest2",
            keccak256("test2")
        );
        
        address[] memory clients = reputationRegistry.getClients(agentId);
        assertEq(clients.length, 2);
        assertTrue(clients[0] == alice || clients[0] == bob);
        assertTrue(clients[1] == alice || clients[1] == bob);
    }

    function test_RevokeFeedback() public {
        vm.prank(alice);
        reputationRegistry.giveFeedback(
            agentId,
            80,
            0,
            "performance",
            "reliability",
            "endpoint",
            "ipfs://QmTest",
            keccak256("test")
        );
        
        vm.expectEmit(true, true, true, true, address(reputationRegistry));
        emit FeedbackRevoked(agentId, alice, 0);
        
        vm.prank(alice);
        reputationRegistry.revokeFeedback(agentId, alice, 0);
        
        (, , , , bool isRevoked) = reputationRegistry.readFeedback(agentId, alice, 0);
        assertTrue(isRevoked);
    }

    function test_RevokeFeedbackUnauthorized() public {
        vm.prank(alice);
        reputationRegistry.giveFeedback(
            agentId,
            80,
            0,
            "performance",
            "reliability",
            "endpoint",
            "ipfs://QmTest",
            keccak256("test")
        );
        
        vm.prank(bob);
        vm.expectRevert(abi.encodeWithSelector(IReputationRegistry.NotAuthorized.selector));
        reputationRegistry.revokeFeedback(agentId, alice, 0);
    }

    function test_RevokeFeedbackAlreadyRevoked() public {
        vm.prank(alice);
        reputationRegistry.giveFeedback(
            agentId,
            80,
            0,
            "performance",
            "reliability",
            "endpoint",
            "ipfs://QmTest",
            keccak256("test")
        );
        
        vm.prank(alice);
        reputationRegistry.revokeFeedback(agentId, alice, 0);
        
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(IReputationRegistry.AlreadyRevoked.selector));
        reputationRegistry.revokeFeedback(agentId, alice, 0);
    }

    function test_AppendResponse() public {
        vm.prank(alice);
        reputationRegistry.giveFeedback(
            agentId,
            80,
            0,
            "performance",
            "reliability",
            "endpoint",
            "ipfs://QmTest",
            keccak256("test")
        );
        
        string memory responseURI = "ipfs://QmResponse";
        bytes32 responseHash = keccak256("response");
        
        vm.expectEmit(true, true, false, true, address(reputationRegistry));
        emit ResponseAppended(agentId, alice, 0, responseURI, responseHash);
        
        reputationRegistry.appendResponse(agentId, alice, 0, responseURI, responseHash);
    }

    function test_AppendResponseUnauthorized() public {
        vm.prank(alice);
        reputationRegistry.giveFeedback(
            agentId,
            80,
            0,
            "performance",
            "reliability",
            "endpoint",
            "ipfs://QmTest",
            keccak256("test")
        );
        
        vm.prank(bob);
        vm.expectRevert(abi.encodeWithSelector(IReputationRegistry.NotAuthorized.selector));
        reputationRegistry.appendResponse(agentId, alice, 0, "ipfs://QmResponse", keccak256("response"));
    }

    function test_GetFeedbackCount() public {
        assertEq(reputationRegistry.getFeedbackCount(agentId, alice), 0);
        
        vm.prank(alice);
        reputationRegistry.giveFeedback(
            agentId,
            80,
            0,
            "performance",
            "reliability",
            "endpoint",
            "ipfs://QmTest",
            keccak256("test")
        );
        
        assertEq(reputationRegistry.getFeedbackCount(agentId, alice), 1);
        
        vm.prank(alice);
        reputationRegistry.giveFeedback(
            agentId,
            90,
            0,
            "security",
            "reliability",
            "endpoint",
            "ipfs://QmTest2",
            keccak256("test2")
        );
        
        assertEq(reputationRegistry.getFeedbackCount(agentId, alice), 2);
    }

    function test_HasFeedback() public {
        assertFalse(reputationRegistry.hasFeedback(agentId, alice));
        
        vm.prank(alice);
        reputationRegistry.giveFeedback(
            agentId,
            80,
            0,
            "performance",
            "reliability",
            "endpoint",
            "ipfs://QmTest",
            keccak256("test")
        );
        
        assertTrue(reputationRegistry.hasFeedback(agentId, alice));
    }

    function test_ReadFeedbackInvalidAgent() public {
        vm.expectRevert(abi.encodeWithSelector(IIdentityRegistry.InvalidAgentId.selector));
        reputationRegistry.readFeedback(999, alice, 0);
    }

    function test_ReadFeedbackInvalidIndex() public {
        vm.prank(alice);
        reputationRegistry.giveFeedback(
            agentId,
            80,
            0,
            "performance",
            "reliability",
            "endpoint",
            "ipfs://QmTest",
            keccak256("test")
        );
        
        vm.expectRevert(abi.encodeWithSelector(IReputationRegistry.InvalidFeedbackIndex.selector));
        reputationRegistry.readFeedback(agentId, alice, 1);
    }

    function test_GetSummaryWithDecimals() public {
        // Give feedback with different decimal precision
        vm.prank(alice);
        reputationRegistry.giveFeedback(
            agentId,
            850, // 8.50 with 2 decimals
            2,
            "performance",
            "reliability",
            "endpoint",
            "ipfs://QmTest1",
            keccak256("test1")
        );
        
        vm.prank(bob);
        reputationRegistry.giveFeedback(
            agentId,
            900, // 9.00 with 2 decimals
            2,
            "performance",
            "reliability",
            "endpoint",
            "ipfs://QmTest2",
            keccak256("test2")
        );
        
        (uint64 count, int128 summaryValue, uint8 summaryDecimals) = 
            reputationRegistry.getSummary(agentId, new address[](0), "", "");
        
        assertEq(count, 2);
        assertEq(summaryValue, 875); // (850 + 900) / 2
        assertEq(summaryDecimals, 2);
    }

    function testFuzz_MultipleFeedback(uint8 count) public {
        vm.assume(count > 0 && count <= 10);
        
        for (uint256 i = 0; i < count; i++) {
            address client = address(uint160(0x100 + i));
            vm.prank(client);
            reputationRegistry.giveFeedback(
                agentId,
                int128(uint128(50 + i * 10)), // Values from 50 to 140
                0,
                "performance",
                "reliability",
                "endpoint",
                "ipfs://QmTest",
                keccak256(abi.encodePacked("test", i))
            );
        }
        
        (uint64 feedbackCount, , ) = reputationRegistry.getSummary(agentId, new address[](0), "", "");
        assertEq(feedbackCount, count);
    }
}
