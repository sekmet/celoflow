"""Tests for real-time status service."""

import asyncio
import json
import logging
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from services.real_time_status import (
    RealTimeStatusService,
    StatusEvent,
    OperationType,
    StatusLogHandler,
    real_time_status_service,
)


@pytest.fixture
def status_service():
    """Create a fresh status service for each test."""
    service = RealTimeStatusService()
    yield service
    service.stop_monitoring()


@pytest.fixture
def sample_log_records():
    """Sample log records for testing."""
    return [
        logging.LogRecord(
            name="remittance_tools",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Auto-swap: 0.07 CELO -> USDm (need 0.05 USDm)",
            args=(),
            exc_info=None,
        ),
        logging.LogRecord(
            name="remittance_tools",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="ERC-20 transfer executed: 1 BRLm -> 0x1234...abcd (tx: 0xabcdef123456)",
            args=(),
            exc_info=None,
        ),
        logging.LogRecord(
            name="remittance_tools",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="Agent wallet has 0.5 but needs 1.0 of BRLm",
            args=(),
            exc_info=None,
        ),
        logging.LogRecord(
            name="compliance_plugin",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Compliance screening passed for user",
            args=(),
            exc_info=None,
        ),
        logging.LogRecord(
            name="remittance_tools",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Transfer reverted: insufficient balance",
            args=(),
            exc_info=None,
        ),
    ]


class TestStatusEvent:
    """Test StatusEvent dataclass."""
    
    def test_status_event_creation(self):
        """Test creating a status event."""
        event = StatusEvent(
            operation=OperationType.SWAPPING,
            message="Auto-swap in progress",
            amount="0.07",
            token="CELO",
            progress=0.5
        )
        
        assert event.operation == OperationType.SWAPPING
        assert event.message == "Auto-swap in progress"
        assert event.amount == "0.07"
        assert event.token == "CELO"
        assert event.progress == 0.5
        assert event.timestamp is not None
        assert isinstance(event.timestamp, float)
    
    def test_status_event_auto_timestamp(self):
        """Test that timestamp is set automatically."""
        before = time.time()
        event = StatusEvent(
            operation=OperationType.TRANSFERRING,
            message="Transfer executing"
        )
        after = time.time()
        
        assert before <= event.timestamp <= after


class TestRealTimeStatusService:
    """Test RealTimeStatusService."""
    
    def test_service_initialization(self, status_service):
        """Test service initialization."""
        assert status_service._subscribers == set()
        assert len(status_service._status_history) == 0
        assert status_service._current_operation is None
        assert status_service._logger_handler is None
    
    def test_operation_patterns(self, status_service):
        """Test operation pattern detection."""
        patterns = status_service._operation_patterns
        
        # Check that all operation types have patterns
        for op_type in OperationType:
            assert op_type in patterns
            assert len(patterns[op_type]) > 0
    
    @pytest.mark.asyncio
    async def test_subscribe_unsubscribe(self, status_service):
        """Test subscribing and unsubscribing from status updates."""
        queue = await status_service.subscribe()
        assert queue in status_service._subscribers
        
        status_service.unsubscribe(queue)
        assert queue not in status_service._subscribers
    
    @pytest.mark.asyncio
    async def test_broadcast_status(self, status_service):
        """Test broadcasting status events."""
        # Subscribe to updates
        queue1 = await status_service.subscribe()
        queue2 = await status_service.subscribe()
        
        # Create and broadcast event
        event = StatusEvent(
            operation=OperationType.SWAPPING,
            message="Test swap",
            amount="1.0",
            token="CELO"
        )
        
        await status_service.broadcast_status(event)
        
        # Check event was broadcast to all subscribers
        assert not queue1.empty()
        assert not queue2.empty()
        
        event1 = await queue1.get()
        event2 = await queue2.get()
        
        assert event1["operation"] == "swapping"
        assert event1["amount"] == "1.0"
        assert event1["token"] == "CELO"
        
        # Both should receive the same event
        assert event1 == event2
    
    @pytest.mark.asyncio
    async def test_broadcast_status_with_full_queue(self, status_service):
        """Test broadcasting when subscriber queue is full."""
        # Create a small queue that will fill up
        queue = asyncio.Queue(maxsize=1)
        status_service._subscribers.add(queue)
        
        # Fill the queue
        await queue.put("test")
        
        # Broadcast event (should handle full queue gracefully)
        event = StatusEvent(
            operation=OperationType.TRANSFERRING,
            message="Test transfer"
        )
        
        await status_service.broadcast_status(event)
        
        # Queue should still be full and subscriber should be removed
        assert queue.full()
        assert queue not in status_service._subscribers
    
    def test_detect_operation_from_log(self, status_service, sample_log_records):
        """Test detecting operations from log messages."""
        test_cases = [
            (sample_log_records[0].msg, OperationType.SWAPPING, {"amount": "0.07", "token": "CELO"}),
            (sample_log_records[1].msg, OperationType.TRANSFERRING, {"amount": "1", "token": "BRLm"}),
            (sample_log_records[2].msg, OperationType.CHECKING_BALANCE, {"current_balance": "0.5", "needed_amount": "1.0", "token": "BRLm"}),
            (sample_log_records[3].msg, OperationType.COMPLIANCE_CHECK, {}),
            (sample_log_records[4].msg, OperationType.ERROR, {"error_message": "Transfer reverted: insufficient balance"}),
        ]
        
        for message, expected_op, expected_details in test_cases:
            event = status_service.detect_operation_from_log(message)
            
            assert event is not None
            assert event.operation == expected_op
            assert event.message == message
            
            for key, value in expected_details.items():
                assert event.details.get(key) == value
    
    def test_detect_operation_no_match(self, status_service):
        """Test when log message doesn't match any operation."""
        message = "This is a regular log message with no operation"
        event = status_service.detect_operation_from_log(message)
        
        assert event is None
    
    def test_extract_details_swap(self, status_service):
        """Test extracting details from swap messages."""
        message = "Auto-swap: 0.07 CELO -> USDm (need 0.05 USDm)"
        details = status_service._extract_details(message, OperationType.SWAPPING)
        
        assert details["amount"] == "0.07"
        assert details["token"] == "CELO"
    
    def test_extract_details_transfer(self, status_service):
        """Test extracting details from transfer messages."""
        message = "ERC-20 transfer executed: 1 BRLm -> 0x1234567890abcdef (tx: 0xabcdef123456)"
        details = status_service._extract_details(message, OperationType.TRANSFERRING)
        
        assert details["amount"] == "1"
        assert details["token"] == "BRLm"
        assert details["recipient"] == "0x1234567890"
        assert details["transaction_hash"] == "0xabcdef123456"
    
    def test_extract_details_hop_progress(self, status_service):
        """Test extracting progress from hop messages."""
        # Test hop1
        message1 = "Auto-swap hop1: need ~0.05 USDm for 1 BRLm"
        details1 = status_service._extract_details(message1, OperationType.SWAPPING)
        assert details1["progress"] == 0.5
        
        # Test hop2
        message2 = "Auto-swap hop2 done: USDm->BRLm tx=0x123456"
        details2 = status_service._extract_details(message2, OperationType.SWAPPING)
        assert details2["progress"] == 1.0
    
    def test_get_current_status(self, status_service):
        """Test getting current status."""
        # Initially should be None
        assert status_service.get_current_status() is None
        
        # Set current operation
        event = StatusEvent(
            operation=OperationType.SWAPPING,
            message="Current swap"
        )
        status_service._current_operation = event
        
        current = status_service.get_current_status()
        assert current["operation"] == "swapping"
        assert current["message"] == "Current swap"
    
    def test_get_status_history(self, status_service):
        """Test getting status history."""
        # Add some events to history
        events = [
            StatusEvent(OperationType.THINKING, "Thinking"),
            StatusEvent(OperationType.ROUTING, "Routing"),
            StatusEvent(OperationType.SWAPPING, "Swapping"),
        ]
        
        for event in events:
            status_service._status_history.append(event)
        
        history = status_service.get_status_history(limit=2)
        assert len(history) == 2
        assert history[0]["operation"] == "routing"
        assert history[1]["operation"] == "swapping"
        
        # Test default limit
        all_history = status_service.get_status_history()
        assert len(all_history) == 3
    
    def test_start_stop_monitoring(self, status_service):
        """Test starting and stopping monitoring."""
        # Initially not monitoring
        assert status_service._logger_handler is None
        
        # Start monitoring
        status_service.start_monitoring()
        assert status_service._logger_handler is not None
        assert isinstance(status_service._logger_handler, StatusLogHandler)
        
        # Stop monitoring
        status_service.stop_monitoring()
        assert status_service._logger_handler is None


class TestStatusLogHandler:
    """Test StatusLogHandler."""
    
    def test_handler_creation(self, status_service):
        """Test creating a log handler."""
        handler = StatusLogHandler(status_service)
        assert handler.status_service == status_service
    
    @patch('asyncio.run')
    def test_emit_with_status_event(self, mock_run, status_service):
        """Test emitting a log record that matches an operation."""
        handler = StatusLogHandler(status_service)
        
        # Mock the broadcast_status method
        status_service.broadcast_status = AsyncMock()
        
        # Create a log record that should match
        record = logging.LogRecord(
            name="remittance_tools",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Auto-swap: 1.0 CELO -> USDm",
            args=(),
            exc_info=None,
        )
        
        handler.emit(record)
        
        # Should have called broadcast_status
        status_service.broadcast_status.assert_called_once()
        
        # Check the event that was broadcast
        call_args = status_service.broadcast_status.call_args[0][0]
        assert isinstance(call_args, StatusEvent)
        assert call_args.operation == OperationType.SWAPPING
        assert call_args.amount == "1.0"
        assert call_args.token == "CELO"
    
    def test_emit_no_match(self, status_service):
        """Test emitting a log record that doesn't match any operation."""
        handler = StatusLogHandler(status_service)
        
        # Mock the broadcast_status method
        status_service.broadcast_status = AsyncMock()
        
        # Create a log record that shouldn't match
        record = logging.LogRecord(
            name="some_logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Regular log message",
            args=(),
            exc_info=None,
        )
        
        handler.emit(record)
        
        # Should not have called broadcast_status
        status_service.broadcast_status.assert_not_called()
    
    def test_emit_with_exception(self, status_service):
        """Test emitting when an exception occurs."""
        handler = StatusLogHandler(status_service)
        
        # Mock detect_operation_from_log to raise an exception
        status_service.detect_operation_from_log = MagicMock(side_effect=Exception("Test error"))
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        # Should not raise exception
        handler.emit(record)


class TestGlobalService:
    """Test the global service instance."""
    
    def test_global_service_exists(self):
        """Test that the global service instance exists."""
        assert real_time_status_service is not None
        assert isinstance(real_time_status_service, RealTimeStatusService)
    
    def test_global_service_singleton(self):
        """Test that the global service is a singleton."""
        from services.real_time_status import real_time_status_service as service2
        
        assert real_time_status_service is service2


@pytest.mark.asyncio
class TestIntegration:
    """Integration tests for the real-time status service."""
    
    async def test_end_to_end_flow(self, status_service):
        """Test end-to-end flow of log monitoring to status broadcast."""
        # Start monitoring
        status_service.start_monitoring()
        
        # Subscribe to updates
        queue = await status_service.subscribe()
        
        # Simulate a log message
        log_message = "Auto-swap hop1: need ~0.05 USDm for 1 BRLm"
        
        # Detect operation from log
        event = status_service.detect_operation_from_log(log_message)
        assert event is not None
        assert event.operation == OperationType.SWAPPING
        assert event.progress == 0.5
        
        # Broadcast the event
        await status_service.broadcast_status(event)
        
        # Check the event was received
        assert not queue.empty()
        received_event = await queue.get()
        assert received_event["operation"] == "swapping"
        assert received_event["progress"] == 0.5
        
        # Clean up
        status_service.stop_monitoring()
