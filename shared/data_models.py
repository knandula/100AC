"""
Data models for 100AC agent system.

Defines the core message and agent data structures used throughout the system.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """Types of messages that can be sent between agents."""
    
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    ALERT = "alert"
    COMMAND = "command"


class Message(BaseModel):
    """
    Standard message format for inter-agent communication.
    
    All messages flowing through the system follow this structure to ensure
    consistent parsing and routing.
    """
    
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    from_agent: str
    to_agent: Optional[str] = None  # None means broadcast
    message_type: MessageType
    topic: str
    data: Dict[str, Any]
    correlation_id: Optional[str] = None  # For request-response tracking
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AgentCapability(BaseModel):
    """Describes a specific capability an agent provides."""
    
    name: str
    description: str
    parameters: Dict[str, str] = Field(default_factory=dict)  # param_name: type
    returns: str = "Dict[str, Any]"


class AgentMetadata(BaseModel):
    """Metadata describing an agent's configuration and capabilities."""
    
    agent_id: str
    name: str
    description: str
    category: str  # data, technical, fundamental, risk, etc.
    capabilities: List[AgentCapability] = Field(default_factory=list)
    subscribes_to: List[str] = Field(default_factory=list)  # Topics to listen to
    publishes_to: List[str] = Field(default_factory=list)  # Topics published
    dependencies: List[str] = Field(default_factory=list)  # Other agent IDs needed
    enabled: bool = True
    version: str = "0.1.0"


class AgentStatus(str, Enum):
    """Current operational status of an agent."""
    
    IDLE = "idle"
    PROCESSING = "processing"
    ERROR = "error"
    DISABLED = "disabled"
    STARTING = "starting"
    STOPPING = "stopping"


class AgentHealth(BaseModel):
    """Health and performance metrics for an agent."""
    
    agent_id: str
    status: AgentStatus
    last_heartbeat: datetime = Field(default_factory=datetime.utcnow)
    messages_processed: int = 0
    errors_count: int = 0
    average_response_time_ms: float = 0.0
    uptime_seconds: float = 0.0
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class WorkflowStep(BaseModel):
    """A single step in a multi-agent workflow."""
    
    step_id: str
    agent_id: str
    action: str  # Capability name to invoke
    parameters: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = 30
    retry_count: int = 0
    on_error: str = "stop"  # stop, continue, retry


class Workflow(BaseModel):
    """Defines a multi-step workflow across agents."""
    
    workflow_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str
    steps: List[WorkflowStep]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
