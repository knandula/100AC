"""
Test Agent - Simple agent for testing the system.

This agent echoes back requests and demonstrates basic agent functionality.
"""

import sys
from pathlib import Path
from typing import Any, Dict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.base_agent import BaseAgent
from shared.data_models import AgentCapability, AgentMetadata, Message


class TestAgent(BaseAgent):
    """
    A simple test agent that echoes requests back.
    
    Used for:
    - Testing the message bus
    - Verifying agent communication
    - Demonstrating basic agent structure
    """
    
    def get_metadata(self) -> AgentMetadata:
        """Return agent metadata."""
        return AgentMetadata(
            agent_id="test_agent",
            name="Test Agent",
            description="Simple test agent for system verification",
            category="infrastructure",
            capabilities=[
                AgentCapability(
                    name="echo",
                    description="Echo back the input data",
                    parameters={"message": "str"},
                    returns="Dict[str, Any]",
                ),
                AgentCapability(
                    name="add",
                    description="Add two numbers",
                    parameters={"a": "float", "b": "float"},
                    returns="Dict[str, float]",
                ),
            ],
            subscribes_to=["test_topic"],
            publishes_to=["test_response"],
        )
    
    async def process_request(self, message: Message) -> Dict[str, Any]:
        """
        Process an incoming request.
        
        Args:
            message: The request message
        
        Returns:
            Response data
        """
        # Echo action - just return the data back
        if message.topic == "echo":
            return {
                "original_data": message.data,
                "agent": self.agent_id,
                "message": "Echo successful",
            }
        
        # Add action - add two numbers
        elif message.topic == "add":
            a = message.data.get("a", 0)
            b = message.data.get("b", 0)
            result = a + b
            return {
                "a": a,
                "b": b,
                "result": result,
                "agent": self.agent_id,
            }
        
        # Unknown action
        else:
            return {
                "error": f"Unknown action: {message.topic}",
                "available_actions": ["echo", "add"],
            }
    
    async def _handle_event(self, message: Message) -> None:
        """Handle event messages."""
        # For testing, just log that we received an event
        if message.topic == "test_topic":
            await self.publish_event(
                topic="test_response",
                data={
                    "received_from": message.from_agent,
                    "data": message.data,
                },
            )
