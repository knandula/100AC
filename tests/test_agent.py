"""
Tests for the test agent.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from agents.test_agent import TestAgent
from shared.data_models import Message, MessageType
from shared.message_bus import MessageBus, init_message_bus


@pytest.mark.asyncio
async def test_test_agent_metadata():
    """Test agent metadata."""
    agent = TestAgent()
    metadata = agent.get_metadata()
    
    assert metadata.agent_id == "test_agent"
    assert metadata.category == "infrastructure"
    assert len(metadata.capabilities) == 2


@pytest.mark.asyncio
async def test_test_agent_echo():
    """Test echo capability."""
    # Initialize message bus
    bus = init_message_bus()
    await bus.start()
    
    # Create agent
    agent = TestAgent()
    await agent.start()
    
    # Send echo request
    request = Message(
        from_agent="tester",
        to_agent="test_agent",
        message_type=MessageType.REQUEST,
        topic="echo",
        data={"message": "hello"},
        correlation_id="test_123",
    )
    
    result = await agent.process_request(request)
    
    assert result["agent"] == "test_agent"
    assert result["original_data"]["message"] == "hello"
    
    await agent.stop()
    await bus.stop()


@pytest.mark.asyncio
async def test_test_agent_add():
    """Test add capability."""
    # Initialize message bus
    bus = init_message_bus()
    await bus.start()
    
    # Create agent
    agent = TestAgent()
    await agent.start()
    
    # Send add request
    request = Message(
        from_agent="tester",
        to_agent="test_agent",
        message_type=MessageType.REQUEST,
        topic="add",
        data={"a": 5, "b": 7},
        correlation_id="test_456",
    )
    
    result = await agent.process_request(request)
    
    assert result["result"] == 12
    assert result["a"] == 5
    assert result["b"] == 7
    
    await agent.stop()
    await bus.stop()
