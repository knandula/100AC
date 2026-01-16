"""
Message Bus - Inter-agent communication system.

Provides pub/sub messaging between agents using an in-memory implementation.
Can be extended to use Redis, RabbitMQ, or other message brokers.
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional
from uuid import uuid4

from loguru import logger

from .data_models import Message, MessageType


class MessageBus:
    """
    In-memory message bus for agent communication.
    
    Supports:
    - Publish/Subscribe pattern
    - Request/Response pattern
    - Message history and replay
    - Topic-based routing
    """
    
    def __init__(self, retention_seconds: int = 3600):
        """
        Initialize the message bus.
        
        Args:
            retention_seconds: How long to keep messages in history
        """
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._message_history: List[Message] = []
        self._retention_seconds = retention_seconds
        self._pending_responses: Dict[str, asyncio.Future] = {}
        self._running = False
        self._cleanup_task: Optional[asyncio.Task] = None
        
        logger.info("MessageBus initialized")
    
    async def start(self) -> None:
        """Start the message bus."""
        if self._running:
            logger.warning("MessageBus already running")
            return
        
        self._running = True
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("MessageBus started")
    
    async def stop(self) -> None:
        """Stop the message bus."""
        if not self._running:
            return
        
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("MessageBus stopped")
    
    def subscribe(self, topic: str, callback: Callable) -> str:
        """
        Subscribe to a topic.
        
        Args:
            topic: Topic name to subscribe to
            callback: Async function to call when message arrives
        
        Returns:
            Subscription ID
        """
        subscription_id = str(uuid4())
        self._subscribers[topic].append(callback)
        logger.debug(f"Subscribed to topic '{topic}'")
        return subscription_id
    
    def unsubscribe(self, topic: str, callback: Callable) -> None:
        """
        Unsubscribe from a topic.
        
        Args:
            topic: Topic name
            callback: Callback function to remove
        """
        if topic in self._subscribers:
            try:
                self._subscribers[topic].remove(callback)
                logger.debug(f"Unsubscribed from topic '{topic}'")
            except ValueError:
                pass
    
    async def publish(self, message: Message) -> None:
        """
        Publish a message to all subscribers of its topic.
        
        Args:
            message: Message to publish
        """
        # Add to history
        self._message_history.append(message)
        
        logger.debug(
            f"Publishing message: {message.message_type} on topic '{message.topic}' "
            f"from {message.from_agent}"
        )
        
        # If this is a response to a pending request, resolve the future
        if message.message_type == MessageType.RESPONSE and message.correlation_id:
            if message.correlation_id in self._pending_responses:
                future = self._pending_responses.pop(message.correlation_id)
                if not future.done():
                    future.set_result(message)
                return
        
        # Notify all subscribers
        subscribers = self._subscribers.get(message.topic, [])
        if not subscribers:
            logger.debug(f"No subscribers for topic '{message.topic}'")
            return
        
        # Call all callbacks
        for callback in subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
            except Exception as e:
                logger.error(f"Error in subscriber callback: {e}")
    
    async def request(
        self,
        from_agent: str,
        to_agent: str,
        topic: str,
        data: dict,
        timeout: float = 30.0,
    ) -> Message:
        """
        Send a request and wait for a response.
        
        Args:
            from_agent: Requesting agent ID
            to_agent: Target agent ID
            topic: Topic for the request
            data: Request data
            timeout: Timeout in seconds
        
        Returns:
            Response message
        
        Raises:
            asyncio.TimeoutError: If response not received within timeout
        """
        correlation_id = str(uuid4())
        
        # Create request message
        request_msg = Message(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=MessageType.REQUEST,
            topic=topic,
            data=data,
            correlation_id=correlation_id,
        )
        
        # Create future for response
        future = asyncio.Future()
        self._pending_responses[correlation_id] = future
        
        # Publish request
        await self.publish(request_msg)
        
        # Wait for response
        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            # Cleanup
            self._pending_responses.pop(correlation_id, None)
            raise
    
    async def respond(
        self,
        original_message: Message,
        from_agent: str,
        data: dict,
    ) -> None:
        """
        Send a response to a request.
        
        Args:
            original_message: The request message being responded to
            from_agent: Responding agent ID
            data: Response data
        """
        if not original_message.correlation_id:
            logger.warning("Cannot respond to message without correlation_id")
            return
        
        response_msg = Message(
            from_agent=from_agent,
            to_agent=original_message.from_agent,
            message_type=MessageType.RESPONSE,
            topic=original_message.topic,
            data=data,
            correlation_id=original_message.correlation_id,
        )
        
        await self.publish(response_msg)
    
    def get_history(
        self,
        topic: Optional[str] = None,
        from_agent: Optional[str] = None,
        limit: int = 100,
    ) -> List[Message]:
        """
        Get message history.
        
        Args:
            topic: Filter by topic
            from_agent: Filter by sender
            limit: Maximum number of messages to return
        
        Returns:
            List of messages
        """
        messages = self._message_history
        
        if topic:
            messages = [m for m in messages if m.topic == topic]
        
        if from_agent:
            messages = [m for m in messages if m.from_agent == from_agent]
        
        return messages[-limit:]
    
    async def _cleanup_loop(self) -> None:
        """Periodically cleanup old messages."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Run every minute
                self._cleanup_old_messages()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    def _cleanup_old_messages(self) -> None:
        """Remove messages older than retention period."""
        if not self._message_history:
            return
        
        cutoff_time = datetime.utcnow() - timedelta(seconds=self._retention_seconds)
        original_count = len(self._message_history)
        
        self._message_history = [
            m for m in self._message_history if m.timestamp > cutoff_time
        ]
        
        removed = original_count - len(self._message_history)
        if removed > 0:
            logger.debug(f"Cleaned up {removed} old messages")


# Global message bus instance
_message_bus: Optional[MessageBus] = None


def get_message_bus() -> MessageBus:
    """Get the global message bus instance."""
    global _message_bus
    if _message_bus is None:
        _message_bus = MessageBus()
    return _message_bus


def init_message_bus(retention_seconds: int = 3600) -> MessageBus:
    """Initialize the global message bus instance."""
    global _message_bus
    _message_bus = MessageBus(retention_seconds)
    return _message_bus
