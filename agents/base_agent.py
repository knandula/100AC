"""
Base Agent - Foundation class for all 100AC agents.

Provides common functionality:
- Message bus integration
- Request/response handling
- Publishing events
- Health tracking
- Claude AI integration
"""

import asyncio
import sys
from pathlib import Path
from abc import ABC, abstractmethod
from datetime import datetime
from time import time
from typing import Any, Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from anthropic import Anthropic
from loguru import logger

from shared.config import get_config
from shared.data_models import (
    AgentHealth,
    AgentMetadata,
    AgentStatus,
    Message,
    MessageType,
)
from shared.message_bus import get_message_bus


class BaseAgent(ABC):
    """
    Base class for all agents in the 100AC system.
    
    Subclasses must implement:
    - get_metadata(): Return agent metadata
    - process_request(): Handle incoming requests
    """
    
    def __init__(self):
        """Initialize the base agent."""
        self.metadata = self.get_metadata()
        self.agent_id = self.metadata.agent_id
        self.message_bus = get_message_bus()
        self.config = get_config()
        
        # Initialize Claude client if API key is available
        self.claude_client: Optional[Anthropic] = None
        if self.config.claude_config.api_key:
            self.claude_client = Anthropic(api_key=self.config.claude_config.api_key)
        
        # Health tracking
        self._health = AgentHealth(
            agent_id=self.agent_id,
            status=AgentStatus.IDLE,
        )
        self._start_time = time()
        self._processing_times: List[float] = []
        
        # Running state
        self._running = False
        self._tasks: List[asyncio.Task] = []
        
        logger.info(f"Agent '{self.agent_id}' initialized")
    
    @abstractmethod
    def get_metadata(self) -> AgentMetadata:
        """
        Return metadata describing this agent.
        
        Must be implemented by subclasses.
        """
        pass
    
    @abstractmethod
    async def process_request(self, message: Message) -> Dict[str, Any]:
        """
        Process an incoming request message.
        
        Args:
            message: The request message
        
        Returns:
            Response data dictionary
        
        Must be implemented by subclasses.
        """
        pass
    
    async def start(self) -> None:
        """Start the agent."""
        if self._running:
            logger.warning(f"Agent '{self.agent_id}' already running")
            return
        
        self._running = True
        self._health.status = AgentStatus.STARTING
        
        # Subscribe to agent's capability topics (for requests)
        for capability in self.metadata.capabilities:
            self.message_bus.subscribe(capability.name, self._handle_message)
            logger.debug(f"Agent '{self.agent_id}' subscribed to capability '{capability.name}'")
        
        # Subscribe to additional topics (for events/alerts)
        for topic in self.metadata.subscribes_to:
            self.message_bus.subscribe(topic, self._handle_message)
            logger.debug(f"Agent '{self.agent_id}' subscribed to topic '{topic}'")
        
        # Start heartbeat task
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._tasks.append(heartbeat_task)
        
        self._health.status = AgentStatus.IDLE
        logger.info(f"Agent '{self.agent_id}' started")
    
    async def stop(self) -> None:
        """Stop the agent."""
        if not self._running:
            return
        
        self._running = False
        self._health.status = AgentStatus.STOPPING
        
        # Unsubscribe from capability topics
        for capability in self.metadata.capabilities:
            self.message_bus.unsubscribe(capability.name, self._handle_message)
        
        # Unsubscribe from additional topics
        for topic in self.metadata.subscribes_to:
            self.message_bus.unsubscribe(topic, self._handle_message)
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        self._health.status = AgentStatus.DISABLED
        logger.info(f"Agent '{self.agent_id}' stopped")
    
    async def _handle_message(self, message: Message) -> None:
        """
        Handle an incoming message.
        
        Routes messages to appropriate handlers based on type.
        """
        # Ignore messages from self
        if message.from_agent == self.agent_id:
            return
        
        # Check if message is for this agent or broadcast
        if message.to_agent and message.to_agent != self.agent_id:
            return
        
        logger.debug(
            f"Agent '{self.agent_id}' received {message.message_type} "
            f"on topic '{message.topic}' from '{message.from_agent}'"
        )
        
        try:
            if message.message_type == MessageType.REQUEST:
                await self._handle_request(message)
            elif message.message_type == MessageType.EVENT:
                await self._handle_event(message)
            elif message.message_type == MessageType.ALERT:
                await self._handle_alert(message)
            elif message.message_type == MessageType.COMMAND:
                await self._handle_command(message)
        except Exception as e:
            logger.error(f"Error handling message in '{self.agent_id}': {e}")
            self._health.errors_count += 1
            self._health.status = AgentStatus.ERROR
    
    async def _handle_request(self, message: Message) -> None:
        """Handle a request message and send response."""
        self._health.status = AgentStatus.PROCESSING
        start_time = time()
        
        try:
            # Process the request
            response_data = await self.process_request(message)
            
            # Send response
            await self.message_bus.respond(
                original_message=message,
                from_agent=self.agent_id,
                data=response_data,
            )
            
            # Update metrics
            processing_time = (time() - start_time) * 1000  # Convert to ms
            self._processing_times.append(processing_time)
            self._health.messages_processed += 1
            
            # Keep only last 100 processing times for average
            if len(self._processing_times) > 100:
                self._processing_times = self._processing_times[-100:]
            
            self._health.average_response_time_ms = sum(self._processing_times) / len(
                self._processing_times
            )
            
        except Exception as e:
            logger.error(f"Error processing request in '{self.agent_id}': {e}")
            self._health.errors_count += 1
            
            # Send error response
            await self.message_bus.respond(
                original_message=message,
                from_agent=self.agent_id,
                data={"error": str(e)},
            )
        finally:
            self._health.status = AgentStatus.IDLE
    
    async def _handle_event(self, message: Message) -> None:
        """Handle an event message (can be overridden by subclasses)."""
        pass
    
    async def _handle_alert(self, message: Message) -> None:
        """Handle an alert message (can be overridden by subclasses)."""
        pass
    
    async def _handle_command(self, message: Message) -> None:
        """Handle a command message (can be overridden by subclasses)."""
        pass
    
    async def publish_event(self, topic: str, data: Dict[str, Any]) -> None:
        """
        Publish an event to a topic.
        
        Args:
            topic: Topic to publish to
            data: Event data
        """
        message = Message(
            from_agent=self.agent_id,
            message_type=MessageType.EVENT,
            topic=topic,
            data=data,
        )
        await self.message_bus.publish(message)
    
    async def publish_alert(self, topic: str, data: Dict[str, Any]) -> None:
        """
        Publish an alert.
        
        Args:
            topic: Topic to publish to
            data: Alert data
        """
        message = Message(
            from_agent=self.agent_id,
            message_type=MessageType.ALERT,
            topic=topic,
            data=data,
        )
        await self.message_bus.publish(message)
    
    async def request_from_agent(
        self,
        to_agent: str,
        topic: str,
        data: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Send a request to another agent and wait for response.
        
        Args:
            to_agent: Target agent ID
            topic: Request topic
            data: Request data
            timeout: Timeout in seconds
        
        Returns:
            Response data
        
        Raises:
            asyncio.TimeoutError: If response not received
        """
        response = await self.message_bus.request(
            from_agent=self.agent_id,
            to_agent=to_agent,
            topic=topic,
            data=data,
            timeout=timeout,
        )
        return response.data
    
    async def call_claude(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Call Claude AI for assistance.
        
        Args:
            prompt: The prompt to send to Claude
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens to generate
        
        Returns:
            Claude's response text
        
        Raises:
            RuntimeError: If Claude client not initialized
        """
        if not self.claude_client:
            raise RuntimeError("Claude client not initialized. Check ANTHROPIC_API_KEY.")
        
        messages = [{"role": "user", "content": prompt}]
        
        kwargs = {
            "model": self.config.claude_config.model,
            "max_tokens": max_tokens or self.config.claude_config.max_tokens,
            "messages": messages,
        }
        
        if system_prompt:
            kwargs["system"] = system_prompt
        
        response = self.claude_client.messages.create(**kwargs)
        return response.content[0].text
    
    def get_health(self) -> AgentHealth:
        """Get current health status."""
        self._health.uptime_seconds = time() - self._start_time
        self._health.last_heartbeat = datetime.utcnow()
        return self._health
    
    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat."""
        while self._running:
            try:
                await asyncio.sleep(30)  # Every 30 seconds
                
                # Publish health status
                await self.publish_event(
                    topic="agent_health",
                    data={
                        "agent_id": self.agent_id,
                        "status": self._health.status.value,
                        "messages_processed": self._health.messages_processed,
                        "errors_count": self._health.errors_count,
                        "uptime_seconds": time() - self._start_time,
                    },
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop for '{self.agent_id}': {e}")
