"""Real-time Status Service — Captures backend operations and provides live status updates."""

import asyncio
import json
import logging
import time
from collections import deque
from contextlib import asynccontextmanager
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, asdict
import re

logger = logging.getLogger(__name__)


class OperationType(str, Enum):
    SWAPPING = "swapping"
    TRANSFERRING = "transferring"
    CHECKING_BALANCE = "checking_balance"
    COMPLIANCE_CHECK = "compliance_check"
    TEE_VERIFICATION = "tee_verification"
    KYC_CHECK = "kyc_check"
    ROUTE_FINDING = "route_finding"
    ERROR = "error"
    IDLE = "idle"


@dataclass
class StatusEvent:
    operation: OperationType
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: float = None
    progress: Optional[float] = None  # 0.0 to 1.0
    transaction_hash: Optional[str] = None
    amount: Optional[str] = None
    token: Optional[str] = None
    recipient: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class RealTimeStatusService:
    """Service for capturing and broadcasting real-time backend operation status."""
    
    def __init__(self):
        self._subscribers: Set[asyncio.Queue] = set()
        self._status_history: deque = deque(maxlen=1000)
        self._current_operation: Optional[StatusEvent] = None
        self._logger_handler: Optional[logging.Handler] = None
        self._operation_patterns = self._init_operation_patterns()
        
    def _init_operation_patterns(self) -> Dict[OperationType, List[re.Pattern]]:
        """Initialize regex patterns for detecting operations from log messages."""
        return {
            OperationType.SWAPPING: [
                re.compile(r'Auto-swap:.*CELO -> USDm', re.IGNORECASE),
                re.compile(r'Auto-swap hop[12]:', re.IGNORECASE),
                re.compile(r'hop[12] done:', re.IGNORECASE),
                re.compile(r'swapping|swap|exchange', re.IGNORECASE),
            ],
            OperationType.TRANSFERRING: [
                re.compile(r'ERC-20 transfer executed:', re.IGNORECASE),
                re.compile(r'Simulated ERC-20 transfer:', re.IGNORECASE),
                re.compile(r'transfer.*->.*tx:', re.IGNORECASE),
                re.compile(r'sending|transferring|payment', re.IGNORECASE),
            ],
            OperationType.CHECKING_BALANCE: [
                re.compile(r'balance.*but needs', re.IGNORECASE),
                re.compile(r'Pre-flight balance check', re.IGNORECASE),
                re.compile(r'check.*balance', re.IGNORECASE),
            ],
            OperationType.COMPLIANCE_CHECK: [
                re.compile(r'Compliance screening', re.IGNORECASE),
                re.compile(r'compliance.*check', re.IGNORECASE),
                re.compile(r'sanction.*check', re.IGNORECASE),
            ],
            OperationType.KYC_CHECK: [
                re.compile(r'KYC check', re.IGNORECASE),
                re.compile(r'kyc.*verification', re.IGNORECASE),
            ],
            OperationType.TEE_VERIFICATION: [
                re.compile(r'TEE.*attestation', re.IGNORECASE),
                re.compile(r'tee.*verification', re.IGNORECASE),
            ],
            OperationType.ROUTE_FINDING: [
                re.compile(r'find_optimal_route', re.IGNORECASE),
                re.compile(r'route.*optimization', re.IGNORECASE),
                re.compile(r'optimal.*route', re.IGNORECASE),
            ],
            OperationType.ERROR: [
                re.compile(r'error|failed|reverted', re.IGNORECASE),
                re.compile(r'exception.*occurred', re.IGNORECASE),
            ],
        }
    
    def start_monitoring(self):
        """Start monitoring backend logs for operation status."""
        if self._logger_handler:
            return  # Already monitoring
            
        # Create custom log handler
        self._logger_handler = StatusLogHandler(self)
        self._logger_handler.setLevel(logging.INFO)
        
        # Add to relevant loggers
        loggers_to_monitor = [
            'remittance_tools',
            'mento_plugin', 
            'compliance_plugin',
            'kyc_plugin',
            'tee_plugin',
            '__main__',
        ]
        
        for logger_name in loggers_to_monitor:
            try:
                log = logging.getLogger(logger_name)
                log.addHandler(self._logger_handler)
            except Exception as e:
                logger.warning(f"Failed to attach status monitor to {logger_name}: {e}")
        
        logger.info("Started real-time status monitoring")
    
    def stop_monitoring(self):
        """Stop monitoring backend logs."""
        if self._logger_handler:
            # Remove handler from all loggers
            for log in logging.Logger.manager.loggerDict.values():
                if hasattr(log, 'handlers') and self._logger_handler in log.handlers:
                    log.removeHandler(self._logger_handler)
            
            self._logger_handler = None
            logger.info("Stopped real-time status monitoring")
    
    async def subscribe(self) -> asyncio.Queue:
        """Subscribe to real-time status updates."""
        queue = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        
        # Send current status immediately
        if self._current_operation:
            await queue.put(asdict(self._current_operation))
        
        return queue
    
    def unsubscribe(self, queue: asyncio.Queue):
        """Unsubscribe from status updates."""
        self._subscribers.discard(queue)
    
    async def broadcast_status(self, event: StatusEvent):
        """Broadcast status event to all subscribers."""
        self._current_operation = event
        self._status_history.append(event)
        
        # Broadcast to all subscribers
        for queue in list(self._subscribers):
            try:
                await queue.put(asdict(event))
            except asyncio.QueueFull:
                # Remove subscriber if queue is full (disconnected)
                self._subscribers.discard(queue)
            except Exception as e:
                logger.warning(f"Failed to broadcast status to subscriber: {e}")
    
    def detect_operation_from_log(self, message: str, level: str = "INFO") -> Optional[StatusEvent]:
        """Detect operation type and extract details from log message."""
        message_lower = message.lower()
        
        # Check each operation type
        for op_type, patterns in self._operation_patterns.items():
            for pattern in patterns:
                if pattern.search(message):
                    # Extract details based on operation type
                    details = self._extract_details(message, op_type)
                    
                    return StatusEvent(
                        operation=op_type,
                        message=message,
                        details=details,
                        amount=details.get('amount'),
                        token=details.get('token'),
                        recipient=details.get('recipient'),
                        transaction_hash=details.get('transaction_hash'),
                        progress=details.get('progress'),
                    )
        
        return None
    
    def _extract_details(self, message: str, op_type: OperationType) -> Dict[str, Any]:
        """Extract operation details from log message."""
        details = {}
        
        if op_type == OperationType.SWAPPING:
            # Extract amounts and tokens
            amount_match = re.search(r'([\d.]+)\s*(\w+)', message)
            if amount_match:
                details['amount'] = amount_match.group(1)
                details['token'] = amount_match.group(2)
            
            # Extract transaction hash
            tx_match = re.search(r'tx=([0-9a-fx]+)', message)
            if tx_match:
                details['transaction_hash'] = tx_match.group(1)
                
            # Extract progress
            if 'hop1' in message:
                details['progress'] = 0.5
            elif 'hop2' in message:
                details['progress'] = 1.0
                
        elif op_type == OperationType.TRANSFERRING:
            # Extract transfer details
            amount_match = re.search(r'([\d.]+)\s*(\w+)\s*->', message)
            if amount_match:
                details['amount'] = amount_match.group(1)
                details['token'] = amount_match.group(2)
            
            # Extract recipient (first 10 chars)
            recipient_match = re.search(r'->\s*([0-9a-f]{10})', message)
            if recipient_match:
                details['recipient'] = recipient_match.group(1)
            
            # Extract transaction hash
            tx_match = re.search(r'tx:\s*([0-9a-fx]+)', message)
            if tx_match:
                details['transaction_hash'] = tx_match.group(1)
                
        elif op_type == OperationType.CHECKING_BALANCE:
            # Extract balance information
            balance_match = re.search(r'has\s*([\d.]+)\s*but needs\s*([\d.]+)\s*(\w+)', message)
            if balance_match:
                details['current_balance'] = balance_match.group(1)
                details['needed_amount'] = balance_match.group(2)
                details['token'] = balance_match.group(3)
                
        elif op_type == OperationType.ERROR:
            # Extract error details
            details['error_message'] = message
            
        return details
    
    def get_current_status(self) -> Optional[Dict[str, Any]]:
        """Get current operation status."""
        if self._current_operation:
            return asdict(self._current_operation)
        return None
    
    def get_status_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent status history."""
        return [asdict(event) for event in list(self._status_history)[-limit:]]


class StatusLogHandler(logging.Handler):
    """Custom log handler that captures operation status from log messages."""
    
    def __init__(self, status_service: RealTimeStatusService):
        super().__init__()
        self.status_service = status_service
    
    def emit(self, record):
        """Handle log record and detect status updates."""
        try:
            message = self.format(record)
            event = self.status_service.detect_operation_from_log(message, record.levelname)
            
            if event:
                # Create asyncio task to broadcast status
                try:
                    loop = asyncio.get_event_loop()
                    loop.create_task(self.status_service.broadcast_status(event))
                except RuntimeError:
                    # No event loop running, create one
                    asyncio.run(self.status_service.broadcast_status(event))
                    
        except Exception as e:
            logger.error(f"StatusLogHandler error: {e}")


# Global instance
real_time_status_service = RealTimeStatusService()
