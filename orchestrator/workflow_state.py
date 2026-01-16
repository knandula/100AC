"""
Workflow State Manager - Tracks workflow execution state and history.

Handles:
- Workflow execution history
- Step-by-step state tracking
- Execution logs
- Performance metrics
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from shared.database.connection import get_database
from shared.database.models import Base
from sqlalchemy import Column, String, DateTime, Integer, JSON, Float
from sqlalchemy import select


class WorkflowExecution(Base):
    """Database model for workflow execution history."""
    
    __tablename__ = "workflow_executions"
    
    execution_id = Column(String(36), primary_key=True)
    workflow_id = Column(String(36), nullable=False, index=True)
    workflow_name = Column(String(200), nullable=False)
    status = Column(String(20), nullable=False)  # running, completed, failed, cancelled
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    context = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    error_message = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class WorkflowStepExecution(Base):
    """Database model for individual step execution within a workflow."""
    
    __tablename__ = "workflow_step_executions"
    
    step_execution_id = Column(String(36), primary_key=True)
    execution_id = Column(String(36), nullable=False, index=True)
    step_id = Column(String(200), nullable=False)
    agent_id = Column(String(200), nullable=False)
    action = Column(String(200), nullable=False)
    status = Column(String(20), nullable=False)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Float, nullable=True)
    parameters = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    error_message = Column(String(1000), nullable=True)
    retry_count = Column(Integer, default=0)


class WorkflowStateManager:
    """
    Manages workflow execution state and history.
    
    Provides:
    - Execution tracking
    - State persistence
    - History queries
    - Performance metrics
    """
    
    def __init__(self):
        """Initialize the state manager."""
        self.db = get_database()
        logger.info("WorkflowStateManager initialized")
    
    async def create_execution(
        self,
        workflow_id: str,
        workflow_name: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a new workflow execution record.
        
        Args:
            workflow_id: The workflow ID
            workflow_name: The workflow name
            context: Initial context data
        
        Returns:
            Execution ID
        """
        execution_id = str(uuid4())
        
        async with self.db.get_session() as session:
            execution = WorkflowExecution(
                execution_id=execution_id,
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                status="running",
                started_at=datetime.utcnow(),
                context=context,
            )
            session.add(execution)
            await session.commit()
        
        logger.info(f"Created workflow execution {execution_id} for '{workflow_name}'")
        return execution_id
    
    async def update_execution(
        self,
        execution_id: str,
        status: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Update a workflow execution record.
        
        Args:
            execution_id: The execution ID
            status: New status
            result: Execution result
            error_message: Error message if failed
        """
        async with self.db.get_session() as session:
            stmt = select(WorkflowExecution).where(
                WorkflowExecution.execution_id == execution_id
            )
            result_obj = await session.execute(stmt)
            execution = result_obj.scalar_one_or_none()
            
            if not execution:
                logger.warning(f"Execution {execution_id} not found")
                return
            
            if status:
                execution.status = status
            
            if result is not None:
                execution.result = result
            
            if error_message:
                execution.error_message = error_message
            
            if status in ("completed", "failed", "cancelled"):
                execution.completed_at = datetime.utcnow()
                duration = (execution.completed_at - execution.started_at).total_seconds()
                execution.duration_seconds = duration
            
            await session.commit()
        
        logger.debug(f"Updated execution {execution_id}: status={status}")
    
    async def create_step_execution(
        self,
        execution_id: str,
        step_id: str,
        agent_id: str,
        action: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a new step execution record.
        
        Args:
            execution_id: Parent workflow execution ID
            step_id: The step ID
            agent_id: The agent ID
            action: The action being performed
            parameters: Step parameters
        
        Returns:
            Step execution ID
        """
        step_execution_id = str(uuid4())
        
        async with self.db.get_session() as session:
            step_execution = WorkflowStepExecution(
                step_execution_id=step_execution_id,
                execution_id=execution_id,
                step_id=step_id,
                agent_id=agent_id,
                action=action,
                status="running",
                started_at=datetime.utcnow(),
                parameters=parameters,
            )
            session.add(step_execution)
            await session.commit()
        
        return step_execution_id
    
    async def update_step_execution(
        self,
        step_execution_id: str,
        status: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        retry_count: Optional[int] = None,
    ) -> None:
        """
        Update a step execution record.
        
        Args:
            step_execution_id: The step execution ID
            status: New status
            result: Step result
            error_message: Error message if failed
            retry_count: Number of retries
        """
        async with self.db.get_session() as session:
            stmt = select(WorkflowStepExecution).where(
                WorkflowStepExecution.step_execution_id == step_execution_id
            )
            result_obj = await session.execute(stmt)
            step_execution = result_obj.scalar_one_or_none()
            
            if not step_execution:
                return
            
            if status:
                step_execution.status = status
            
            if result is not None:
                step_execution.result = result
            
            if error_message:
                step_execution.error_message = error_message
            
            if retry_count is not None:
                step_execution.retry_count = retry_count
            
            if status in ("completed", "failed", "cancelled"):
                step_execution.completed_at = datetime.utcnow()
                duration = (step_execution.completed_at - step_execution.started_at).total_seconds()
                step_execution.duration_ms = duration * 1000
            
            await session.commit()
    
    async def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a workflow execution record.
        
        Args:
            execution_id: The execution ID
        
        Returns:
            Execution data or None
        """
        async with self.db.get_session() as session:
            stmt = select(WorkflowExecution).where(
                WorkflowExecution.execution_id == execution_id
            )
            result = await session.execute(stmt)
            execution = result.scalar_one_or_none()
            
            if not execution:
                return None
            
            return {
                "execution_id": execution.execution_id,
                "workflow_id": execution.workflow_id,
                "workflow_name": execution.workflow_name,
                "status": execution.status,
                "started_at": execution.started_at.isoformat(),
                "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                "duration_seconds": execution.duration_seconds,
                "context": execution.context,
                "result": execution.result,
                "error_message": execution.error_message,
            }
    
    async def get_workflow_history(
        self,
        workflow_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get workflow execution history.
        
        Args:
            workflow_id: Filter by workflow ID (optional)
            limit: Maximum number of records
        
        Returns:
            List of execution records
        """
        async with self.db.get_session() as session:
            stmt = select(WorkflowExecution).order_by(
                WorkflowExecution.started_at.desc()
            ).limit(limit)
            
            if workflow_id:
                stmt = stmt.where(WorkflowExecution.workflow_id == workflow_id)
            
            result = await session.execute(stmt)
            executions = result.scalars().all()
            
            return [
                {
                    "execution_id": exe.execution_id,
                    "workflow_id": exe.workflow_id,
                    "workflow_name": exe.workflow_name,
                    "status": exe.status,
                    "started_at": exe.started_at.isoformat(),
                    "completed_at": exe.completed_at.isoformat() if exe.completed_at else None,
                    "duration_seconds": exe.duration_seconds,
                    "error_message": exe.error_message,
                }
                for exe in executions
            ]
    
    async def get_step_executions(
        self,
        execution_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get all step executions for a workflow execution.
        
        Args:
            execution_id: The workflow execution ID
        
        Returns:
            List of step execution records
        """
        async with self.db.get_session() as session:
            stmt = select(WorkflowStepExecution).where(
                WorkflowStepExecution.execution_id == execution_id
            ).order_by(WorkflowStepExecution.started_at)
            
            result = await session.execute(stmt)
            steps = result.scalars().all()
            
            return [
                {
                    "step_execution_id": step.step_execution_id,
                    "step_id": step.step_id,
                    "agent_id": step.agent_id,
                    "action": step.action,
                    "status": step.status,
                    "started_at": step.started_at.isoformat(),
                    "completed_at": step.completed_at.isoformat() if step.completed_at else None,
                    "duration_ms": step.duration_ms,
                    "error_message": step.error_message,
                    "retry_count": step.retry_count,
                }
                for step in steps
            ]
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get overall workflow execution statistics.
        
        Returns:
            Statistics dict
        """
        async with self.db.get_session() as session:
            # Count total executions
            stmt = select(WorkflowExecution)
            result = await session.execute(stmt)
            all_executions = result.scalars().all()
            
            total = len(all_executions)
            completed = sum(1 for e in all_executions if e.status == "completed")
            failed = sum(1 for e in all_executions if e.status == "failed")
            running = sum(1 for e in all_executions if e.status == "running")
            
            # Average duration
            completed_with_duration = [
                e for e in all_executions
                if e.status == "completed" and e.duration_seconds
            ]
            avg_duration = (
                sum(e.duration_seconds for e in completed_with_duration) / len(completed_with_duration)
                if completed_with_duration else 0
            )
            
            return {
                "total_executions": total,
                "completed": completed,
                "failed": failed,
                "running": running,
                "success_rate": (completed / total * 100) if total > 0 else 0,
                "average_duration_seconds": avg_duration,
            }


# Global state manager instance
_state_manager: Optional[WorkflowStateManager] = None


def get_state_manager() -> WorkflowStateManager:
    """Get the global workflow state manager instance."""
    global _state_manager
    if _state_manager is None:
        _state_manager = WorkflowStateManager()
    return _state_manager


def init_state_manager() -> WorkflowStateManager:
    """Initialize the global workflow state manager instance."""
    global _state_manager
    _state_manager = WorkflowStateManager()
    return _state_manager
