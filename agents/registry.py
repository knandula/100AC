"""
Agent Registry - Central registry for all agents in the system.

Manages agent registration, discovery, and lifecycle.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from agents.base_agent import BaseAgent
from shared.data_models import AgentMetadata


class AgentRegistry:
    """
    Central registry for managing all agents.
    
    Provides:
    - Agent registration and discovery
    - Capability lookup
    - Dependency resolution
    """
    
    def __init__(self):
        """Initialize the agent registry."""
        self._agents: Dict[str, BaseAgent] = {}
        self._metadata: Dict[str, AgentMetadata] = {}
        logger.info("AgentRegistry initialized")
    
    def register(self, agent: BaseAgent) -> None:
        """
        Register an agent.
        
        Args:
            agent: The agent instance to register
        """
        agent_id = agent.metadata.agent_id
        
        if agent_id in self._agents:
            logger.warning(f"Agent '{agent_id}' already registered, replacing")
        
        self._agents[agent_id] = agent
        self._metadata[agent_id] = agent.metadata
        
        logger.info(f"Registered agent '{agent_id}' ({agent.metadata.category})")
    
    def unregister(self, agent_id: str) -> None:
        """
        Unregister an agent.
        
        Args:
            agent_id: ID of agent to unregister
        """
        if agent_id in self._agents:
            del self._agents[agent_id]
            del self._metadata[agent_id]
            logger.info(f"Unregistered agent '{agent_id}'")
        else:
            logger.warning(f"Agent '{agent_id}' not found in registry")
    
    def get(self, agent_id: str) -> Optional[BaseAgent]:
        """
        Get an agent by ID.
        
        Args:
            agent_id: The agent ID
        
        Returns:
            The agent instance or None if not found
        """
        return self._agents.get(agent_id)
    
    def get_metadata(self, agent_id: str) -> Optional[AgentMetadata]:
        """
        Get agent metadata by ID.
        
        Args:
            agent_id: The agent ID
        
        Returns:
            The agent metadata or None if not found
        """
        return self._metadata.get(agent_id)
    
    def get_all_agents(self) -> List[BaseAgent]:
        """
        Get all registered agents.
        
        Returns:
            List of all agents
        """
        return list(self._agents.values())
    
    def get_all_metadata(self) -> List[AgentMetadata]:
        """
        Get metadata for all registered agents.
        
        Returns:
            List of all agent metadata
        """
        return list(self._metadata.values())
    
    def find_by_category(self, category: str) -> List[BaseAgent]:
        """
        Find agents by category.
        
        Args:
            category: The category to search for
        
        Returns:
            List of agents in that category
        """
        return [
            agent
            for agent in self._agents.values()
            if agent.metadata.category == category
        ]
    
    def find_by_capability(self, capability_name: str) -> List[BaseAgent]:
        """
        Find agents that have a specific capability.
        
        Args:
            capability_name: The capability to search for
        
        Returns:
            List of agents with that capability
        """
        agents = []
        for agent in self._agents.values():
            for cap in agent.metadata.capabilities:
                if cap.name == capability_name:
                    agents.append(agent)
                    break
        return agents
    
    def get_dependencies(self, agent_id: str) -> List[str]:
        """
        Get the dependencies of an agent.
        
        Args:
            agent_id: The agent ID
        
        Returns:
            List of agent IDs that this agent depends on
        """
        metadata = self._metadata.get(agent_id)
        if metadata:
            return metadata.dependencies
        return []
    
    def check_dependencies(self, agent_id: str) -> bool:
        """
        Check if all dependencies of an agent are registered.
        
        Args:
            agent_id: The agent ID
        
        Returns:
            True if all dependencies are available
        """
        dependencies = self.get_dependencies(agent_id)
        return all(dep_id in self._agents for dep_id in dependencies)
    
    def get_agent_count(self) -> int:
        """Get the total number of registered agents."""
        return len(self._agents)
    
    def get_categories(self) -> List[str]:
        """Get all unique categories."""
        return list(set(meta.category for meta in self._metadata.values()))
    
    async def start_all(self) -> None:
        """Start all registered agents."""
        logger.info(f"Starting {len(self._agents)} agents...")
        
        for agent in self._agents.values():
            if agent.metadata.enabled:
                try:
                    await agent.start()
                except Exception as e:
                    logger.error(f"Failed to start agent '{agent.agent_id}': {e}")
        
        logger.info("All agents started")
    
    async def stop_all(self) -> None:
        """Stop all registered agents."""
        logger.info(f"Stopping {len(self._agents)} agents...")
        
        for agent in self._agents.values():
            try:
                await agent.stop()
            except Exception as e:
                logger.error(f"Failed to stop agent '{agent.agent_id}': {e}")
        
        logger.info("All agents stopped")


# Global registry instance
_registry: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    """Get the global agent registry."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


def init_registry() -> AgentRegistry:
    """Initialize the global agent registry."""
    global _registry
    _registry = AgentRegistry()
    return _registry
