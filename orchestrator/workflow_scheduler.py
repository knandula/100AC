"""
Workflow Scheduler - Manages automated workflow execution.

Handles:
- Time-based scheduling (cron-like)
- Event-triggered workflows
- Workflow queuing
- Concurrency control
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from shared.data_models import Workflow
from agents.orchestrator import get_orchestrator


class ScheduledWorkflow:
    """A workflow with scheduling information."""
    
    def __init__(
        self,
        workflow: Workflow,
        schedule_type: str = "manual",  # manual, interval, cron, event
        interval_seconds: Optional[int] = None,
        cron_expression: Optional[str] = None,
        event_topic: Optional[str] = None,
        enabled: bool = True,
    ):
        self.workflow = workflow
        self.schedule_type = schedule_type
        self.interval_seconds = interval_seconds
        self.cron_expression = cron_expression
        self.event_topic = event_topic
        self.enabled = enabled
        self.last_run: Optional[datetime] = None
        self.next_run: Optional[datetime] = None
        self.run_count = 0
        self.error_count = 0


class WorkflowScheduler:
    """
    Manages workflow scheduling and execution.
    
    Supports:
    - Interval-based scheduling (every N seconds)
    - Event-triggered workflows
    - Manual workflow execution
    - Concurrent workflow execution with limits
    """
    
    def __init__(self, max_concurrent_workflows: int = 5):
        """
        Initialize the workflow scheduler.
        
        Args:
            max_concurrent_workflows: Maximum number of workflows to run concurrently
        """
        self.orchestrator = get_orchestrator()
        self.max_concurrent_workflows = max_concurrent_workflows
        
        self._scheduled_workflows: Dict[str, ScheduledWorkflow] = {}
        self._running_workflows: Dict[str, asyncio.Task] = {}
        self._workflow_queue: asyncio.Queue = asyncio.Queue()
        
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._executor_task: Optional[asyncio.Task] = None
        
        logger.info("WorkflowScheduler initialized")
    
    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            logger.warning("WorkflowScheduler already running")
            return
        
        self._running = True
        
        # Start scheduler loop (checks schedules)
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        
        # Start executor loop (runs queued workflows)
        self._executor_task = asyncio.create_task(self._executor_loop())
        
        logger.info("WorkflowScheduler started")
    
    async def stop(self) -> None:
        """Stop the scheduler."""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel scheduler and executor tasks
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        if self._executor_task:
            self._executor_task.cancel()
            try:
                await self._executor_task
            except asyncio.CancelledError:
                pass
        
        # Cancel all running workflows
        for workflow_id, task in list(self._running_workflows.items()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        logger.info("WorkflowScheduler stopped")
    
    def schedule_workflow(
        self,
        workflow: Workflow,
        schedule_type: str = "manual",
        interval_seconds: Optional[int] = None,
        cron_expression: Optional[str] = None,
        event_topic: Optional[str] = None,
    ) -> str:
        """
        Schedule a workflow for execution.
        
        Args:
            workflow: The workflow to schedule
            schedule_type: Type of schedule (manual, interval, cron, event)
            interval_seconds: For interval scheduling
            cron_expression: For cron scheduling (future)
            event_topic: For event-triggered workflows
        
        Returns:
            Schedule ID
        """
        scheduled = ScheduledWorkflow(
            workflow=workflow,
            schedule_type=schedule_type,
            interval_seconds=interval_seconds,
            cron_expression=cron_expression,
            event_topic=event_topic,
        )
        
        # Calculate next run time for interval schedules
        if schedule_type == "interval" and interval_seconds:
            scheduled.next_run = datetime.utcnow() + timedelta(seconds=interval_seconds)
        
        schedule_id = workflow.workflow_id
        self._scheduled_workflows[schedule_id] = scheduled
        
        logger.info(
            f"Scheduled workflow '{workflow.name}' ({schedule_id}) "
            f"with type '{schedule_type}'"
        )
        
        return schedule_id
    
    async def execute_workflow_now(
        self,
        workflow: Workflow,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a workflow immediately (blocking).
        
        Args:
            workflow: The workflow to execute
            context: Initial context data
        
        Returns:
            Workflow execution result
        """
        logger.info(f"Executing workflow '{workflow.name}' immediately")
        
        try:
            result = await self.orchestrator.execute_workflow(workflow, context)
            logger.info(f"Workflow '{workflow.name}' completed successfully")
            return result
        except Exception as e:
            logger.error(f"Workflow '{workflow.name}' failed: {e}")
            raise
    
    async def queue_workflow(
        self,
        workflow: Workflow,
        context: Optional[Dict[str, Any]] = None,
        priority: int = 0,
    ) -> None:
        """
        Queue a workflow for async execution.
        
        Args:
            workflow: The workflow to queue
            context: Initial context data
            priority: Priority (higher = runs sooner, future feature)
        """
        await self._workflow_queue.put((workflow, context))
        logger.info(f"Queued workflow '{workflow.name}' for execution")
    
    def get_scheduled_workflows(self) -> List[ScheduledWorkflow]:
        """Get all scheduled workflows."""
        return list(self._scheduled_workflows.values())
    
    def get_running_workflows(self) -> List[str]:
        """Get IDs of currently running workflows."""
        return list(self._running_workflows.keys())
    
    def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a scheduled workflow.
        
        Args:
            workflow_id: The workflow ID
        
        Returns:
            Status dict or None if not found
        """
        scheduled = self._scheduled_workflows.get(workflow_id)
        if not scheduled:
            return None
        
        return {
            "workflow_id": workflow_id,
            "name": scheduled.workflow.name,
            "schedule_type": scheduled.schedule_type,
            "enabled": scheduled.enabled,
            "last_run": scheduled.last_run.isoformat() if scheduled.last_run else None,
            "next_run": scheduled.next_run.isoformat() if scheduled.next_run else None,
            "run_count": scheduled.run_count,
            "error_count": scheduled.error_count,
            "is_running": workflow_id in self._running_workflows,
        }
    
    async def _scheduler_loop(self) -> None:
        """Main scheduler loop that checks schedules and queues workflows."""
        while self._running:
            try:
                await asyncio.sleep(1)  # Check every second
                
                now = datetime.utcnow()
                
                for schedule_id, scheduled in list(self._scheduled_workflows.items()):
                    # Skip if disabled
                    if not scheduled.enabled:
                        continue
                    
                    # Skip if already running
                    if schedule_id in self._running_workflows:
                        continue
                    
                    # Check if it's time to run
                    should_run = False
                    
                    if scheduled.schedule_type == "interval":
                        if scheduled.next_run and now >= scheduled.next_run:
                            should_run = True
                            # Schedule next run
                            scheduled.next_run = now + timedelta(
                                seconds=scheduled.interval_seconds
                            )
                    
                    if should_run:
                        logger.info(
                            f"Triggering scheduled workflow '{scheduled.workflow.name}'"
                        )
                        await self.queue_workflow(scheduled.workflow)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
    
    async def _executor_loop(self) -> None:
        """Main executor loop that runs queued workflows."""
        while self._running:
            try:
                # Wait for a workflow to be queued
                workflow, context = await asyncio.wait_for(
                    self._workflow_queue.get(),
                    timeout=1.0
                )
                
                # Check concurrency limit
                while len(self._running_workflows) >= self.max_concurrent_workflows:
                    await asyncio.sleep(0.1)
                
                # Execute workflow in background
                task = asyncio.create_task(
                    self._execute_workflow_with_tracking(workflow, context)
                )
                self._running_workflows[workflow.workflow_id] = task
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in executor loop: {e}")
    
    async def _execute_workflow_with_tracking(
        self,
        workflow: Workflow,
        context: Optional[Dict[str, Any]],
    ) -> None:
        """
        Execute a workflow with tracking and cleanup.
        
        Args:
            workflow: The workflow to execute
            context: Initial context
        """
        workflow_id = workflow.workflow_id
        
        # Update scheduled workflow info
        if workflow_id in self._scheduled_workflows:
            scheduled = self._scheduled_workflows[workflow_id]
            scheduled.last_run = datetime.utcnow()
        
        try:
            logger.info(f"Starting workflow '{workflow.name}' ({workflow_id})")
            
            result = await self.orchestrator.execute_workflow(workflow, context)
            
            logger.info(f"Workflow '{workflow.name}' completed successfully")
            
            # Update run count
            if workflow_id in self._scheduled_workflows:
                self._scheduled_workflows[workflow_id].run_count += 1
            
        except Exception as e:
            logger.error(f"Workflow '{workflow.name}' failed: {e}")
            
            # Update error count
            if workflow_id in self._scheduled_workflows:
                self._scheduled_workflows[workflow_id].error_count += 1
        
        finally:
            # Cleanup
            if workflow_id in self._running_workflows:
                del self._running_workflows[workflow_id]


# Global scheduler instance
_scheduler: Optional[WorkflowScheduler] = None


def get_scheduler() -> WorkflowScheduler:
    """Get the global workflow scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = WorkflowScheduler()
    return _scheduler


def init_scheduler(max_concurrent_workflows: int = 5) -> WorkflowScheduler:
    """Initialize the global workflow scheduler instance."""
    global _scheduler
    _scheduler = WorkflowScheduler(max_concurrent_workflows)
    return _scheduler
