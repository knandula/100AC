"""
Tests for the message bus.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from shared.data_models import Message, MessageType
from shared.message_bus import MessageBus


@pytest.mark.asyncio
async def test_message_bus_init():
    """Test message bus initialization."""
    bus = MessageBus(retention_seconds=100)
    assert bus._retention_seconds == 100
    assert not bus._running


@pytest.mark.asyncio
async def test_message_bus_start_stop():
    """Test starting and stopping the message bus."""
    bus = MessageBus()
    
    await bus.start()
    assert bus._running
    
    await bus.stop()
    assert not bus._running


@pytest.mark.asyncio
async def test_subscribe_and_publish():
    """Test subscribing to topics and publishing messages."""
    bus = MessageBus()
    await bus.start()
    
    received_messages = []
    
    async def callback(message: Message):
        received_messages.append(message)
    
    # Subscribe to topic
    bus.subscribe("test_topic", callback)
    
    # Publish message
    message = Message(
        from_agent="test_agent",
        message_type=MessageType.EVENT,
        topic="test_topic",
        data={"key": "value"},
    )
    await bus.publish(message)
    
    # Give time for processing
    await asyncio.sleep(0.1)
    
    # Check message was received
    assert len(received_messages) == 1
    assert received_messages[0].data["key"] == "value"
    
    await bus.stop()


@pytest.mark.asyncio
async def test_request_response():
    """Test request-response pattern."""
    bus = MessageBus()
    await bus.start()
    
    # Set up responder
    async def responder(message: Message):
        if message.message_type == MessageType.REQUEST:
            await bus.respond(
                original_message=message,
                from_agent="responder",
                data={"result": "success"},
            )
    
    bus.subscribe("request_topic", responder)
    
    # Send request and wait for response
    response = await bus.request(
        from_agent="requester",
        to_agent="responder",
        topic="request_topic",
        data={"query": "test"},
        timeout=5.0,
    )
    
    assert response.data["result"] == "success"
    assert response.message_type == MessageType.RESPONSE
    
    await bus.stop()


@pytest.mark.asyncio
async def test_message_history():
    """Test message history tracking."""
    bus = MessageBus()
    await bus.start()
    
    # Publish some messages
    for i in range(5):
        message = Message(
            from_agent=f"agent_{i}",
            message_type=MessageType.EVENT,
            topic="test_topic",
            data={"index": i},
        )
        await bus.publish(message)
    
    # Get history
    history = bus.get_history(topic="test_topic", limit=10)
    assert len(history) == 5
    
    # Get filtered history
    history = bus.get_history(from_agent="agent_0")
    assert len(history) == 1
    assert history[0].data["index"] == 0
    
    await bus.stop()
