"""
Orchestrator - Manages multi-agent workflows and coordination.

Coordinates complex workflows involving multiple agents working together.
"""

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from agents.registry import get_registry
from shared.data_models import Message, MessageType, Workflow, WorkflowStep
from shared.message_bus import get_message_bus


class WorkflowExecutionError(Exception):
    """Raised when a workflow execution fails."""
    pass


class Orchestrator:
    """
    Orchestrates multi-agent workflows.
    
    Manages:
    - Workflow execution
    - Step sequencing
    - Error handling
    - Timeout management
    """
    
    def __init__(self):
        """Initialize the orchestrator."""
        self.registry = get_registry()
        self.message_bus = get_message_bus()
        self._active_workflows: Dict[str, asyncio.Task] = {}
        logger.info("Orchestrator initialized")
    
    async def execute_workflow(
        self,
        workflow: Workflow,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a workflow.
        
        Args:
            workflow: The workflow to execute
            context: Initial context data passed between steps
        
        Returns:
            Final workflow result
        
        Raises:
            WorkflowExecutionError: If workflow fails
        """
        workflow_id = workflow.workflow_id
        logger.info(f"Executing workflow '{workflow.name}' ({workflow_id})")
        
        context = context or {}
        results = {}
        
        try:
            for step in workflow.steps:
                logger.debug(
                    f"Executing step '{step.step_id}' - "
                    f"Agent: {step.agent_id}, Action: {step.action}"
                )
                
                # Execute the step
                step_result = await self._execute_step(step, context)
                
                # Store result
                results[step.step_id] = step_result
                
                # Update context with result
                context[f"step_{step.step_id}"] = step_result
            
            logger.info(f"Workflow '{workflow.name}' completed successfully")
            return results
            
        except Exception as e:
            logger.error(f"Workflow '{workflow.name}' failed: {e}")
            raise WorkflowExecutionError(f"Workflow execution failed: {e}")
    
    async def _execute_step(
        self,
        step: WorkflowStep,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a single workflow step.
        
        Args:
            step: The step to execute
            context: Current workflow context
        
        Returns:
            Step result
        
        Raises:
            WorkflowExecutionError: If step fails
        """
        # Get the agent
        agent = self.registry.get(step.agent_id)
        if not agent:
            raise WorkflowExecutionError(
                f"Agent '{step.agent_id}' not found in registry"
            )
        
        # Check if agent is enabled
        if not agent.metadata.enabled:
            raise WorkflowExecutionError(
                f"Agent '{step.agent_id}' is disabled"
            )
        
        # Merge step parameters with context
        parameters = {**context, **step.parameters}
        
        # Send request to agent
        try:
            result = await self._send_request_with_retry(
                agent_id=step.agent_id,
                action=step.action,
                parameters=parameters,
                timeout=step.timeout_seconds,
                retry_count=step.retry_count,
            )
            return result
            
        except asyncio.TimeoutError:
            if step.on_error == "continue":
                logger.warning(f"Step '{step.step_id}' timed out, continuing")
                return {"error": "timeout"}
            else:
                raise WorkflowExecutionError(
                    f"Step '{step.step_id}' timed out after {step.timeout_seconds}s"
                )
        
        except Exception as e:
            if step.on_error == "continue":
                logger.warning(f"Step '{step.step_id}' failed: {e}, continuing")
                return {"error": str(e)}
            elif step.on_error == "retry" and step.retry_count > 0:
                logger.warning(f"Step '{step.step_id}' failed: {e}, retrying")
                # Retry is handled in _send_request_with_retry
                raise
            else:
                raise WorkflowExecutionError(f"Step '{step.step_id}' failed: {e}")
    
    async def _send_request_with_retry(
        self,
        agent_id: str,
        action: str,
        parameters: Dict[str, Any],
        timeout: float,
        retry_count: int,
    ) -> Dict[str, Any]:
        """
        Send a request to an agent with retry logic.
        
        Args:
            agent_id: Target agent ID
            action: Action to perform
            parameters: Request parameters
            timeout: Request timeout
            retry_count: Number of retries
        
        Returns:
            Response data
        """
        last_error = None
        
        for attempt in range(retry_count + 1):
            try:
                response = await self.message_bus.request(
                    from_agent="orchestrator",
                    to_agent=agent_id,
                    topic=action,
                    data=parameters,
                    timeout=timeout,
                )
                
                # Check for errors in response
                if "error" in response.data:
                    raise WorkflowExecutionError(
                        f"Agent returned error: {response.data['error']}"
                    )
                
                return response.data
                
            except Exception as e:
                last_error = e
                if attempt < retry_count:
                    logger.warning(
                        f"Request to '{agent_id}' failed (attempt {attempt + 1}), retrying: {e}"
                    )
                    await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
        
        raise last_error
    
    async def execute_simple_request(
        self,
        agent_id: str,
        action: str,
        parameters: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Execute a simple single-agent request.
        
        Args:
            agent_id: Target agent ID
            action: Action to perform
            parameters: Request parameters
            timeout: Request timeout
        
        Returns:
            Response data
            
        Raises:
            WorkflowExecutionError: If agent not found or request fails
        """
        # Verify agent exists and is enabled
        agent = self.registry.get(agent_id)
        if not agent:
            error_msg = f"Agent '{agent_id}' not found. Available agents: {[a.agent_id for a in self.registry.get_all_agents()]}"
            logger.error(error_msg)
            raise WorkflowExecutionError(error_msg)
        
        if not agent.metadata.enabled:
            error_msg = f"Agent '{agent_id}' is disabled"
            logger.error(error_msg)
            raise WorkflowExecutionError(error_msg)
        
        # Verify action is a valid capability
        valid_capabilities = [cap.name for cap in agent.metadata.capabilities]
        if action not in valid_capabilities:
            error_msg = f"Action '{action}' not found for agent '{agent_id}'. Valid capabilities: {valid_capabilities}"
            logger.error(error_msg)
            raise WorkflowExecutionError(error_msg)
        
        try:
            return await self._send_request_with_retry(
                agent_id=agent_id,
                action=action,
                parameters=parameters,
                timeout=timeout,
                retry_count=0,
            )
        except asyncio.TimeoutError:
            error_msg = f"Request to agent '{agent_id}' action '{action}' timed out after {timeout}s"
            logger.error(error_msg)
            raise WorkflowExecutionError(error_msg)
        except Exception as e:
            error_msg = f"Request to agent '{agent_id}' action '{action}' failed: {e}"
            logger.error(error_msg)
            raise WorkflowExecutionError(error_msg)
    
    def create_workflow(
        self,
        name: str,
        description: str,
        steps: List[Dict[str, Any]],
    ) -> Workflow:
        """
        Create a workflow from a simple configuration.
        
        Args:
            name: Workflow name
            description: Workflow description
            steps: List of step configurations
        
        Returns:
            Workflow instance
        """
        workflow_steps = []
        for i, step_config in enumerate(steps):
            step = WorkflowStep(
                step_id=step_config.get("step_id", f"step_{i+1}"),
                agent_id=step_config["agent_id"],
                action=step_config["action"],
                parameters=step_config.get("parameters", {}),
                timeout_seconds=step_config.get("timeout_seconds", 30),
                retry_count=step_config.get("retry_count", 0),
                on_error=step_config.get("on_error", "stop"),
            )
            workflow_steps.append(step)
        
        return Workflow(
            name=name,
            description=description,
            steps=workflow_steps,
        )


# Global orchestrator instance
_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    """Get the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator


def init_orchestrator() -> Orchestrator:
    """Initialize the global orchestrator instance."""
    global _orchestrator
    _orchestrator = Orchestrator()
    return _orchestrator
